"""Job-advert extraction. §15"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app import ai
from app.auth import current_user
from app.models import ExtractionRequest, ExtractionResult

router = APIRouter(
    prefix="/api/ai",
    tags=["ai"],
    dependencies=[Depends(current_user)],
)


@router.post(
    "/extract-job-advert",
    response_model=ExtractionResult,
    summary="Extract structured job details from a pasted advert",
)
def extract_job_advert(payload: ExtractionRequest) -> ExtractionResult:
    """Returns a draft for the user to check, never a saved card (§15.3).
    Nothing here is persisted."""
    return ai.extract(payload.advert)
