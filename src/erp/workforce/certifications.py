"""Machine Operator Safety Certification Verifier (PRD §Workforce Agent)."""

from datetime import date

from pydantic import BaseModel


class OperatorCertification(BaseModel):
    certification_code: str
    certification_name: str
    issue_date: date
    expiry_date: date
    is_active: bool = True


class CertificationVerifier:
    """Verifies that operators hold valid, unexpired safety certifications before equipment operation."""

    # Default registry of employee certifications for demonstration
    _operator_certs: dict[str, list[OperatorCertification]] = {
        "EMP-OPERATOR-01": [
            OperatorCertification(
                certification_code="CERT-CNC-5AXIS",
                certification_name="5-Axis CNC Machining Safety & Setup",
                issue_date=date(2025, 1, 15),
                expiry_date=date(2027, 1, 15),
                is_active=True,
            ),
            OperatorCertification(
                certification_code="CERT-INJECTION-MOLD",
                certification_name="Industrial Polymer Injection Molding Level 2",
                issue_date=date(2025, 3, 10),
                expiry_date=date(2027, 3, 10),
                is_active=True,
            ),
        ],
        "EMP-OPERATOR-02": [
            OperatorCertification(
                certification_code="CERT-CNC-5AXIS",
                certification_name="5-Axis CNC Machining Safety & Setup",
                issue_date=date(2024, 6, 1),
                expiry_date=date(2026, 6, 1),
                is_active=True,
            ),
        ],
        "EMP-OPERATOR-TRAINEE": [],
    }

    def verify_operator_certification(
        self,
        employee_code: str,
        required_certification_code: str,
        shift_date: date | None = None,
    ) -> bool:
        """Asserts that the employee holds an active, non-expired certification."""
        today = shift_date or date.today()
        certs = self._operator_certs.get(employee_code, [])
        for c in certs:
            if c.certification_code == required_certification_code and c.is_active:
                if c.expiry_date >= today:
                    return True
        return False


certification_verifier = CertificationVerifier()
