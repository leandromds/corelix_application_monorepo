"""
Reports schemas — Pydantic models for report endpoints.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class SessionReportRequest(BaseModel):
    """Request parameters for session report."""

    start_date: date
    end_date: date


class SessionReportResponse(BaseModel):
    """Response for session report."""

    period_start: date
    period_end: date
    total_sessions: int
    completed_sessions: int
    cancelled_sessions: int
    no_show_sessions: int
    completion_rate: float


class RevenueReportResponse(BaseModel):
    """Response for revenue report."""

    period_start: date
    period_end: date
    total_revenue: Decimal
    average_session_price: Decimal
    sessions_count: int


class AIInsightResponse(BaseModel):
    """Response for AI-generated insights."""

    insights: str
    generated_at: str
