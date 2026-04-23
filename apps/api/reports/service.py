"""
Reports service — business logic for reports and AI insights.

Responsibilities:
- Aggregate session data for reports
- Calculate revenue metrics
- Generate AI-powered insights via ai/service.py
"""

from sqlalchemy.ext.asyncio import AsyncSession


class ReportsService:
    """Handles reports and analytics business logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # TODO: Implement after repository layer is ready
    # Methods to implement:
    # - get_session_report(professional_id, start_date, end_date) -> SessionReport
    # - get_revenue_report(professional_id, period) -> RevenueReport
    # - get_ai_insights(professional_id) -> AIInsightsReport
