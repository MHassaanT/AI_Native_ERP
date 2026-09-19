"""Edge Vision Quality Defect Classifier and PLC Diverter (PRD §Quality Control)."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class DefectClassification(BaseModel):
    inspection_id: str
    item_code: str
    lot_number: str
    workstation_code: str
    defect_type: str  # SURFACE_CRACK, DIMENSIONAL_VARIANCE, VOID, COLOR_DRIFT, NONE
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    is_defective: bool
    trigger_plc_scrap_trip: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EdgeQualityEvaluator:
    """Classifies part defects and commands hardware PLC diversion when confidence > 0.98."""

    PLC_TRIP_CONFIDENCE_THRESHOLD = 0.98

    @staticmethod
    def evaluate_inspection(
        inspection_id: str,
        item_code: str,
        lot_number: str,
        workstation_code: str,
        defect_type: str,
        confidence_score: float,
    ) -> DefectClassification:
        """Evaluates defect classification and triggers PLC trip if confidence > 0.98."""
        is_defective = defect_type.upper() != "NONE" and confidence_score >= 0.50
        trigger_plc = (
            is_defective and confidence_score >= EdgeQualityEvaluator.PLC_TRIP_CONFIDENCE_THRESHOLD
        )

        return DefectClassification(
            inspection_id=inspection_id,
            item_code=item_code,
            lot_number=lot_number,
            workstation_code=workstation_code,
            defect_type=defect_type,
            confidence_score=confidence_score,
            is_defective=is_defective,
            trigger_plc_scrap_trip=trigger_plc,
        )


quality_evaluator = EdgeQualityEvaluator()
