"""
Reports router — billing report endpoint.

Design notes:
- Query params are received individually and assembled into a BillingReportRequest.
  Pydantic model_validator (date range check) runs at construction time — any
  validation failure is caught here and re-raised as CoreValidationError (422)
  so the client receives a structured error instead of a generic 500.
- The professional record is fetched to obtain full_name and specialty, which
  are passed to the service layer for AI context generation.
- AI insights degrade gracefully: if the AI provider is unavailable the report
  is still returned with ai_insights=null (handled in the service layer).
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError as PydanticValidationError

from core.deps import CurrentProfessionalId, TenantSession
from core.exceptions import NotFoundError
from core.exceptions import ValidationError as CoreValidationError
from professionals.repository import ProfessionalsRepository
from reports.schemas import BillingReportRequest, BillingReportResponse, PeriodSummaryResponse
from reports.service import ReportsService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/summary", response_model=PeriodSummaryResponse)
async def get_period_summary(
    db: TenantSession,
    professional_id: CurrentProfessionalId,
    start_date: date = Query(..., description="Period start (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Period end (YYYY-MM-DD)"),
    status_filter: list[str] = Query(
        default=["completed"],
        description="Session statuses to include",
    ),
) -> PeriodSummaryResponse:
    """
    Lightweight period summary for dashboard KPI cards.

    Returns only total_sessions and total_amount — does not aggregate by
    client and does not invoke the AI service. Designed for low-latency
    dashboard widgets.

    **Status filter:**
    - Defaults to `["completed"]`
    - Accepted values: `completed`, `cancelled`, `no_show`, `scheduled`
    - Pass the parameter multiple times:
      `?status_filter=completed&status_filter=no_show`
    """
    try:
        # Reuse BillingReportRequest validation for date range rules
        BillingReportRequest(
            start_date=start_date,
            end_date=end_date,
            status_filter=status_filter,
        )
    except PydanticValidationError as exc:
        errors = jsonable_encoder(exc.errors(include_url=False))
        first_msg = (
            errors[0].get("msg", "Invalid report parameters")
            if errors
            else "Invalid report parameters"
        )
        raise CoreValidationError(
            message=first_msg,
            detail={"errors": errors},
        ) from exc

    service = ReportsService(db)
    return await service.get_period_summary(
        start_date=start_date,
        end_date=end_date,
        status_filter=status_filter,
    )


@router.get("/billing", response_model=BillingReportResponse)
async def get_billing_report(
    db: TenantSession,
    professional_id: CurrentProfessionalId,
    start_date: date = Query(..., description="Period start (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Period end (YYYY-MM-DD)"),
    client_id: UUID | None = Query(default=None, description="Filter by client"),
    status_filter: list[str] = Query(
        default=["completed"],
        description="Session statuses to include",
    ),
) -> BillingReportResponse:
    """
    Generate a billing report for the authenticated professional.

    Aggregates sessions in the requested period by client.
    Appends AI-generated insights when data is available (degrades gracefully
    to ai_insights=null if the AI provider is unavailable).

    **Date range rules:**
    - `end_date` must be >= `start_date`
    - Range cannot exceed 365 days

    **Status filter:**
    - Defaults to `["completed"]`
    - Accepted values: `completed`, `cancelled`, `no_show`, `scheduled`
    - Pass the parameter multiple times to include several statuses:
      `?status_filter=completed&status_filter=no_show`
    """
    prof_repo = ProfessionalsRepository(db)
    professional = await prof_repo.find_by_id(UUID(professional_id))
    if professional is None:
        raise NotFoundError("Professional not found")

    try:
        billing_request = BillingReportRequest(
            start_date=start_date,
            end_date=end_date,
            client_id=client_id,
            status_filter=status_filter,
        )
    except PydanticValidationError as exc:
        # Re-raise as a structured 422 so the caller gets a consistent error
        # format instead of the generic 500 produced by the catch-all handler.
        # jsonable_encoder is required here because exc.errors() may contain
        # non-JSON-serialisable objects (e.g. date values in the error context).
        # This is the same pattern used by the RequestValidationError handler
        # in main.py.
        errors = jsonable_encoder(exc.errors(include_url=False))
        first_msg = (
            errors[0].get("msg", "Invalid report parameters")
            if errors
            else "Invalid report parameters"
        )
        raise CoreValidationError(
            message=first_msg,
            detail={"errors": errors},
        ) from exc

    service = ReportsService(db)
    return await service.generate_billing_report(
        professional_name=professional.full_name,
        professional_specialty=professional.specialty,
        request=billing_request,
    )
