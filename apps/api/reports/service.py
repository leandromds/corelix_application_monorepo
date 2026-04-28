"""
Reports service — business logic for billing reports and AI insights.

Responsibilities:
- Fetch sessions for period via repository
- Aggregate by client in Python (ADR justification in domain docs)
- Generate AI insights via AIService (with graceful degradation)
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ai.prompts import PROMPTS
from ai.service import AIService
from core.exceptions import ExternalServiceError
from reports.repository import ReportsRepository
from reports.schemas import (
    BillingReportRequest,
    BillingReportResponse,
    ClientBillingEntry,
    SessionEntry,
)


class ReportsService:
    def __init__(self, db: AsyncSession) -> None:
        self.repository = ReportsRepository(db)
        self.ai = AIService()

    async def generate_billing_report(
        self,
        professional_name: str,
        professional_specialty: str | None,
        request: BillingReportRequest,
    ) -> BillingReportResponse:
        rows = await self.repository.find_sessions_in_period(
            start_date=request.start_date,
            end_date=request.end_date,
            client_id=request.client_id,
            status_filter=request.status_filter,
        )

        clients_map: dict[UUID, ClientBillingEntry] = {}
        total_amount = Decimal("0")

        for row in rows:
            entry = SessionEntry(
                session_id=row.id,
                client_id=row.client_id,
                client_name=row.client_name,
                scheduled_at=row.scheduled_at,
                duration_minutes=row.duration_minutes,
                price=row.price,
                status=row.status,
                notes=row.notes,
            )

            if row.client_id not in clients_map:
                clients_map[row.client_id] = ClientBillingEntry(
                    client_id=row.client_id,
                    client_name=row.client_name,
                    session_count=0,
                    total_amount=Decimal("0"),
                    sessions=[],
                )

            client_entry = clients_map[row.client_id]
            client_entry.sessions.append(entry)
            client_entry.session_count += 1
            client_entry.total_amount += row.price
            total_amount += row.price

        ai_insights: str | None = None
        if rows:
            try:
                ai_insights = await self._generate_ai_insights(
                    professional_name=professional_name,
                    professional_specialty=professional_specialty,
                    rows=rows,
                    total_amount=total_amount,
                )
            except ExternalServiceError:
                ai_insights = None

        return BillingReportResponse(
            period_start=request.start_date,
            period_end=request.end_date,
            total_sessions=len(rows),
            total_amount=total_amount,
            clients=list(clients_map.values()),
            ai_insights=ai_insights,
            generated_at=datetime.now(UTC),
        )

    async def _generate_ai_insights(
        self,
        professional_name: str,
        professional_specialty: str | None,
        rows: list,
        total_amount: Decimal,
    ) -> str:
        no_show_count = sum(1 for r in rows if r.status == "no_show")
        cancelled_count = sum(1 for r in rows if r.status == "cancelled")

        no_show_by_client: dict[str, int] = {}
        for row in rows:
            if row.status == "no_show":
                no_show_by_client[row.client_name] = no_show_by_client.get(row.client_name, 0) + 1

        specialty = professional_specialty or "profissional"
        unique_clients = list(dict.fromkeys(r.client_name for r in rows))

        context = (
            f"Profissional: {professional_name} ({specialty})\n"
            f"Total de sessões no período: {len(rows)}\n"
            f"Total faturado: R$ {total_amount}\n"
            f"Faltas (no_show): {no_show_count}\n"
            f"Cancelamentos: {cancelled_count}\n"
            "\nClientes com faltas:\n"
            + (
                "\n".join(
                    f"- {name}: {count} falta(s)" for name, count in no_show_by_client.items()
                )
                or "Nenhum"
            )
            + "\n\nClientes atendidos:\n"
            + "\n".join(f"- {name}" for name in unique_clients)
        )

        return await self.ai.complete(
            system_prompt=PROMPTS["report_insights"],
            user_message=context,
        )
