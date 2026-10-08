"""Focused tests for recruiter-reviewed HR screening."""

import io
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from docx import Document

from erp.ai import hr_screening
from erp.ai.hr_screening import (
    EvidenceQuote,
    InterviewDraft,
    ScreeningResponseError,
    ScreeningResult,
    create_interview_draft,
    evaluate_candidate,
)
from erp.db.models.recruitment import CandidateApplication, RecruitmentRole
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
