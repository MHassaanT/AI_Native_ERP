"""Focused tests for recruiter-reviewed HR screening."""

import base64
import importlib.util
import io
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from docx import Document

from erp.ai import hr_screening
from erp.ai.hr_screening import (
    ApplicationEmailAnalysis,
    EvidenceQuote,
    InterviewDraft,
    ScreeningResponseError,
    ScreeningResult,
    create_interview_draft,
    evaluate_candidate,
)
from erp.db.models.recruitment import (
    CandidateApplication,
    CandidateTalentPoolProspect,
    RecruitmentEmailReview,
    RecruitmentRole,
)
from erp.workflows.hr.recruitment_service import RecruitmentService
from erp.workflows.hr.resume_parser import extract_resume_text


def test_recruitment_endpoints_are_in_openapi():
    from erp.api.app import app

    paths = app.openapi()["paths"]
    assert "/api/v1/hr/recruitment/roles" in paths
    assert "/api/v1/hr/recruitment/roles/{role_id}/applications" in paths
    assert "/api/v1/hr/recruitment/applications/{application_id}/evaluate" in paths
    assert "/api/v1/hr/recruitment/applications/{application_id}/interview-draft" in paths
    assert "/api/v1/hr/recruitment/applications/{application_id}" in paths
    assert "/api/v1/hr/recruitment/email-inbox" in paths
    assert "/api/v1/hr/recruitment/email-inbox/{message_id}/analyze" in paths
    assert "/api/v1/hr/recruitment/talent-pool" in paths
    assert "/api/v1/hr/recruitment/roles/{role_id}/match-talent-pool" in paths


def test_configured_gemini_key_is_used_when_openrouter_key_is_missing(monkeypatch):
    monkeypatch.setattr(hr_screening.settings, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(hr_screening.settings, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(hr_screening.settings, "GEMINI_API_KEY", "test-gemini-key")

    assert hr_screening._selected_provider() == "gemini"


def test_explicit_provider_is_respected_when_both_keys_exist(monkeypatch):
    monkeypatch.setattr(hr_screening.settings, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(hr_screening.settings, "OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setattr(hr_screening.settings, "GEMINI_API_KEY", "test-gemini-key")

    assert hr_screening._selected_provider() == "openrouter"


@pytest.mark.parametrize(
    "configured_model",
    [
        "gemini-2.5-flash",
        "models/gemini-2.5-flash",
        "google/gemini-2.5-flash",
    ],
)
def test_gemini_model_name_accepts_common_provider_prefixes(monkeypatch, configured_model):
    monkeypatch.setattr(hr_screening.settings, "GEMINI_MODEL", configured_model)

    assert hr_screening._gemini_model_name() == "gemini-2.5-flash"


def test_gemini_model_name_rejects_openrouter_model_namespace(monkeypatch):
    monkeypatch.setattr(hr_screening.settings, "GEMINI_MODEL", "google/gemini/model-name")

    with pytest.raises(hr_screening.ScreeningConfigurationError, match="GEMINI_MODEL"):
        hr_screening._gemini_model_name()


def test_agent_removal_revision_fits_alembic_version_column():
    revision_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "014_remove_autonomous_workforce_and_hitl.py"
    )
    spec = importlib.util.spec_from_file_location("migration_014", revision_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert len(migration.revision) <= 32


def test_hr_email_pool_migration_follows_recruitment_revision():
    migration_path = (
        Path(__file__).parents[1] / "alembic" / "versions" / "016_hr_email_talent_pool.py"
    )
    spec = importlib.util.spec_from_file_location("migration_016", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "016_hr_email_pool"
    assert len(migration.revision) <= 32
    assert migration.down_revision == "015_hr_recruitment"


def test_pending_talent_pool_migration_follows_whatsapp_revision():
    migration_path = (
        Path(__file__).parents[1] / "alembic" / "versions/018_hr_talent_pool_review.py"
    )
    spec = importlib.util.spec_from_file_location("migration_018", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "018_hr_talent_pool_review"
    assert len(migration.revision) <= 32
    assert migration.down_revision == "017_whatsapp_support_channel"


def test_resume_parser_extracts_docx_text_and_discards_no_text():
    document = Document()
    document.add_paragraph("Experienced backend engineer with Python and SQL experience.")
    output = io.BytesIO()
    document.save(output)

    result = extract_resume_text(
        "candidate.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        output.getvalue(),
    )
    assert "Python and SQL" in result


def test_resume_parser_extracts_pdf_text():
    from reportlab.pdfgen import canvas

    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawString(72, 720, "Experienced engineer with Python API experience.")
    pdf.save()

    result = extract_resume_text("candidate.pdf", "application/pdf", output.getvalue())
    assert "Python API experience" in result


@pytest.mark.parametrize(
    ("filename", "content_type", "content", "error"),
    [
        ("candidate.pdf", "application/pdf", b"not a pdf", "valid PDF and DOCX"),
        ("candidate.txt", "text/plain", b"a" * 30, "Only valid PDF and DOCX"),
        (
            "candidate.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            b"PK",
            "could not be read",
        ),
    ],
)
def test_resume_parser_rejects_invalid_uploads(filename, content_type, content, error):
    with pytest.raises(ValueError, match=error):
        extract_resume_text(filename, content_type, content)


def test_recruitment_models_enforce_tenant_role_relationship_and_score_range():
    application_constraints = {
        constraint.name: constraint
        for constraint in CandidateApplication.__table__.constraints
        if constraint.name
    }
    assert "fk_candidate_application_role_tenant" in application_constraints
    assert "ck_candidate_application_score" in application_constraints
    assert "tenant_id" in RecruitmentRole.__table__.columns
    assert "uq_recruitment_email_review_message" in {
        constraint.name for constraint in RecruitmentEmailReview.__table__.constraints
    }
    assert "fk_recruitment_email_review_inbound_tenant" in {
        constraint.name for constraint in RecruitmentEmailReview.__table__.constraints
    }
    assert "uq_talent_pool_source_review" in {
        constraint.name for constraint in CandidateTalentPoolProspect.__table__.constraints
    }
    pool_status = next(
        constraint.sqltext
        for constraint in CandidateTalentPoolProspect.__table__.constraints
        if constraint.name == "ck_talent_pool_prospect_status"
    )
    assert "PENDING_REVIEW" in str(pool_status)


@pytest.mark.asyncio
async def test_analyzed_application_is_staged_for_pool_without_an_open_role(monkeypatch):
    from erp.api.routes import hr

    tenant_id = uuid.uuid4()
    message = SimpleNamespace(
        message_id="gmail-message-1",
        subject="Sales Manager application",
        sender="Jordan Lee <jordan@example.com>",
        body_text="I am applying for the Sales Manager role.",
    )
    review = SimpleNamespace(status="REVIEW_REQUIRED")
    service = hr.recruitment_service
    monkeypatch.setattr(service, "get_inbound_email", AsyncMock(return_value=message))
    monkeypatch.setattr(service, "get_email_review_by_message", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "list_roles", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        service,
        "create_email_review",
        AsyncMock(return_value=review),
    )
    stage_review = AsyncMock()
    monkeypatch.setattr(service, "stage_email_review_in_talent_pool", stage_review)
    monkeypatch.setattr(
        hr,
        "analyze_application_email",
        AsyncMock(
            return_value=ApplicationEmailAnalysis(
                is_application=True,
                applicant_name="Jordan Lee",
                desired_role="Sales Manager",
                suggested_role_id=None,
                confidence=0.95,
                summary="The sender says they are applying for Sales Manager.",
                evidence=[
                    EvidenceQuote(
                        requirement="Application intent",
                        quote="I am applying for the Sales Manager role.",
                        assessment="The sender explicitly states application intent.",
                    )
                ],
            )
        ),
    )
    monkeypatch.setattr(hr, "_email_review_response", lambda _review: {"status": "REVIEW_REQUIRED"})
    db = AsyncMock()

    response = await hr.analyze_recruitment_email("gmail-message-1", tenant_id, db)

    assert response["status"] == "REVIEW_REQUIRED"
    service.list_roles.assert_awaited_once_with(db, tenant_id, "OPEN")
    stage_review.assert_awaited_once_with(db, tenant_id, review)


@pytest.mark.asyncio
async def test_stage_email_review_creates_pending_candidate_without_duplicate(monkeypatch):
    service = RecruitmentService()
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
        add=Mock(),
        flush=AsyncMock(),
    )
    tenant_id = uuid.uuid4()
    review = RecruitmentEmailReview(
        tenant_id=tenant_id,
        applicant_name="Jordan Lee",
        applicant_email="jordan@example.com",
        desired_role="Sales Manager",
        resume_text="I am applying for Sales Manager.",
    )
    review.review_id = uuid.uuid4()

    prospect = await service.stage_email_review_in_talent_pool(db, tenant_id, review)

    assert prospect.status == "PENDING_REVIEW"
    assert prospect.source_review_id == review.review_id
    db.add.assert_called_once_with(prospect)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_application_email_analysis_checks_exact_evidence_and_role_id(monkeypatch):
    role_id = str(uuid.uuid4())

    async def fake_request_json(_prompt: str):
        return {
            "is_application": True,
            "applicant_name": "Ada Candidate",
            "desired_role": "Backend Engineer",
            "suggested_role_id": role_id,
            "confidence": 0.91,
            "summary": "The message asks to be considered for backend engineering.",
            "evidence": [
                {
                    "requirement": "Application intent",
                    "quote": "I am applying for the backend engineer role.",
                    "assessment": "The sender explicitly states application intent.",
                }
            ],
        }

    monkeypatch.setattr(hr_screening, "_request_json", fake_request_json)
    result = await hr_screening.analyze_application_email(
        subject="Backend Engineer application",
        sender="Ada <ada@example.com>",
        body_text="I am applying for the backend engineer role.",
        roles=[
            {
                "role_id": role_id,
                "title": "Backend Engineer",
                "description": "Build backend services.",
                "requirements": "Python and APIs.",
            }
        ],
    )

    assert isinstance(result, ApplicationEmailAnalysis)
    assert result.suggested_role_id == role_id


@pytest.mark.asyncio
async def test_application_email_analysis_rejects_unverified_evidence(monkeypatch):
    async def fake_request_json(_prompt: str):
        return {
            "is_application": True,
            "applicant_name": None,
            "desired_role": None,
            "suggested_role_id": None,
            "confidence": 0.5,
            "summary": "Potential application.",
            "evidence": [
                {
                    "requirement": "Application intent",
                    "quote": "I invented this quote.",
                    "assessment": "Suggests interest.",
                }
            ],
        }

    monkeypatch.setattr(hr_screening, "_request_json", fake_request_json)
    with pytest.raises(ScreeningResponseError, match="could not be verified"):
        await hr_screening.analyze_application_email(
            subject="Question",
            sender="candidate@example.com",
            body_text="I have a question.",
            roles=[],
        )


def test_gmail_parser_uses_full_plain_text_body_and_nested_attachment():
    from erp.events.gmail_integration import gmail_service

    body = "I am applying for the engineer position and have five years of Python experience."
    encoded_body = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    parsed = gmail_service._parse_gmail_message_payload(
        {
            "id": "gmail-message-id",
            "snippet": "Short snippet",
            "payload": {
                "headers": [
                    {"name": "from", "value": "Candidate <candidate@example.com>"},
                    {"name": "to", "value": "hr@example.com"},
                    {"name": "subject", "value": "Engineer application"},
                ],
                "mimeType": "multipart/mixed",
                "parts": [
                    {
                        "mimeType": "multipart/alternative",
                        "parts": [
                            {
                                "mimeType": "text/plain",
                                "body": {"data": encoded_body},
                            }
                        ],
                    },
                    {
                        "filename": "resume.pdf",
                        "mimeType": "application/pdf",
                        "body": {"size": 42},
                    },
                ],
            },
        },
        str(uuid.uuid4()),
    )

    assert parsed is not None
    assert parsed.body_text == body
    assert [attachment.filename for attachment in parsed.attachments] == ["resume.pdf"]


@pytest.mark.asyncio
async def test_evaluate_candidate_redacts_contact_details_and_checks_evidence(monkeypatch):
    captured: dict[str, str] = {}

    async def fake_request_json(prompt: str):
        captured["prompt"] = prompt
        return {
            "score": 84,
            "summary": "The resume shows relevant backend experience.",
            "matched_requirements": ["Python API development"],
            "evidence": [
                {
                    "requirement": "Python API development",
                    "quote": "Built Python APIs for internal services.",
                    "assessment": "Direct experience developing APIs.",
                }
            ],
        }

    monkeypatch.setattr(hr_screening, "_request_json", fake_request_json)
    result = await evaluate_candidate(
        role_title="Backend Engineer",
        role_description="Build backend services.",
        role_requirements="Python API development",
        resume_text=(
            "Contact candidate@example.com, +1 555-867-5309. "
            "Built Python APIs for internal services."
        ),
    )

    assert isinstance(result, ScreeningResult)
    assert result.score == 84
    assert "candidate@example.com" not in captured["prompt"]
    assert "555-867-5309" not in captured["prompt"]
    assert "protected/personal traits" in captured["prompt"]


@pytest.mark.asyncio
async def test_evaluate_candidate_rejects_unverifiable_evidence(monkeypatch):
    async def fake_request_json(_prompt: str):
        return {
            "score": 100,
            "summary": "Strong candidate.",
            "matched_requirements": ["Python"],
            "evidence": [
                {
                    "requirement": "Python",
                    "quote": "Invented evidence not present in this resume.",
                    "assessment": "Supports Python experience.",
                }
            ],
        }

    monkeypatch.setattr(hr_screening, "_request_json", fake_request_json)
    with pytest.raises(ScreeningResponseError, match="could not be verified"):
        await evaluate_candidate(
            role_title="Engineer",
            role_description="Build software.",
            role_requirements="Python",
            resume_text="This candidate has a short resume.",
        )


@pytest.mark.asyncio
async def test_gemini_api_failure_reports_model_and_provider_reason(monkeypatch):
    from erp.ai.hr_screening import ScreeningProviderError

    captured: list[str] = []

    class ErrorResponse:
        is_error = True
        status_code = 404

        @staticmethod
        def json():
            return {"error": {"message": "Model not found."}}

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, url, **_kwargs):
            captured.append(url)
            return ErrorResponse()

    monkeypatch.setattr(hr_screening.settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(hr_screening.settings, "GEMINI_API_KEY", "test-secret")
    monkeypatch.setattr(hr_screening.settings, "GEMINI_MODEL", "google/gemini-2.5-flash")
    monkeypatch.setattr(hr_screening.httpx, "AsyncClient", FakeClient)

    with pytest.raises(
        ScreeningProviderError,
        match="Gemini returned HTTP 404 for model 'gemini-2.5-flash': Model not found.",
    ):
        await hr_screening._request_json("test prompt")

    assert len(captured) == 1
    assert "/models/gemini-2.5-flash:generateContent" in captured[-1]
    assert "test-secret" not in str(captured)


@pytest.mark.asyncio
async def test_gemini_model_404_retries_supported_fallback(monkeypatch):
    class ModelResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self.is_error = status_code >= 400
            self.payload = payload

        def json(self):
            return self.payload

        def raise_for_status(self):
            if self.is_error:
                raise AssertionError("unexpected error response")

    class FakeClient:
        def __init__(self, **_kwargs):
            self.requests = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, _url, **_kwargs):
            self.requests += 1
            if self.requests == 1:
                return ModelResponse(404, {"error": {"message": "Model not found."}})
            return ModelResponse(
                200,
                {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]},
            )

    monkeypatch.setattr(hr_screening.settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(hr_screening.settings, "GEMINI_API_KEY", "test-secret")
    monkeypatch.setattr(hr_screening.settings, "GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setattr(hr_screening.httpx, "AsyncClient", FakeClient)

    assert await hr_screening._request_json("test prompt") == {"ok": True}


@pytest.mark.asyncio
async def test_interview_draft_is_structured_and_does_not_send_email(monkeypatch):
    captured: dict[str, str] = {}

    async def fake_request_json(_prompt: str):
        captured["prompt"] = _prompt
        return {
            "subject": "Interview discussion: Backend Engineer",
            "body": "Hello Candidate,\n\nCould we discuss your application?",
        }

    monkeypatch.setattr(hr_screening, "_request_json", fake_request_json)
    draft = await create_interview_draft(
        candidate_name="Candidate",
        role_title="Backend Engineer",
        interview_details="Proposed meeting over video call next Tuesday.",
    )
    assert isinstance(draft, InterviewDraft)
    assert "Backend Engineer" in draft.subject
    assert "video call next Tuesday" in captured["prompt"]


@pytest.mark.asyncio
async def test_application_creation_requires_open_tenant_role(monkeypatch):
    service = RecruitmentService()
    db = AsyncMock()
    role = SimpleNamespace(status="CLOSED")
    monkeypatch.setattr(service, "get_role", AsyncMock(return_value=role))

    with pytest.raises(ValueError, match="closed job opening"):
        await service.create_application(
            db,
            uuid.uuid4(),
            uuid.uuid4(),
            None,
            None,
            "candidate.pdf",
            "application/pdf",
            "Extracted resume text with enough content.",
        )
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_recruitment_service_saves_tenant_scoped_evaluation(monkeypatch):
    from erp.api.routes import hr

    tenant_id = uuid.uuid4()
    role_id = uuid.uuid4()
    application = CandidateApplication(
        tenant_id=tenant_id,
        role_id=role_id,
        applicant_name="Candidate",
        applicant_email="candidate@example.com",
        resume_filename="candidate.docx",
        resume_content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        resume_text="Resume text.",
        created_at=datetime.now(UTC),
    )
    application.application_id = uuid.uuid4()
    role = RecruitmentRole(
        tenant_id=tenant_id,
        title="Engineer",
        description="Build services.",
        requirements="Python",
        created_at=datetime.now(UTC),
    )
    role.role_id = role_id
    service = hr.recruitment_service
    get_application = AsyncMock(return_value=application)
    get_role = AsyncMock(return_value=role)
    monkeypatch.setattr(service, "get_application", get_application)
    monkeypatch.setattr(service, "get_role", get_role)
    monkeypatch.setattr(
        hr,
        "evaluate_candidate",
        AsyncMock(
            return_value=ScreeningResult(
                score=84,
                summary="Relevant experience.",
                matched_requirements=["Python"],
                evidence=[
                    EvidenceQuote(
                        requirement="Python",
                        quote="Uses Python.",
                        assessment="Relevant development experience.",
                    )
                ],
            )
        ),
    )
    db = AsyncMock()

    response = await hr.evaluate_candidate_application(
        application.application_id,
        tenant_id,
        db,
    )

    get_application.assert_awaited_once_with(db, tenant_id, application.application_id)
    get_role.assert_awaited_once_with(db, tenant_id, role_id)
    assert response["status"] == "EVALUATED"
    assert response["screening_score"] == 84
    db.flush.assert_awaited_once()
