"""
Tests for ReportsRepository.

Coverage:
- find_sessions_in_period: date range, client_id filter, status filter, empty result
- find_sessions_in_period: RLS — sessions de outro tenant não aparecem
- find_sessions_in_period: join retorna client_name corretamente
- get_period_summary: count + sum corretos
- get_period_summary: coalesce → retorna 0 (não None) quando sem sessões
- get_period_summary: filtra por status

RLS isolation tests follow the same pattern as tests/clients/test_repository.py:
  1. Create other-tenant data WITHOUT switching role (postgres has BYPASSRLS).
  2. Manually SET LOCAL ROLE + SET LOCAL app.current_tenant in the test body.
  3. Query — RLS hides the other tenant's rows.

WHY the RLS test does NOT request `tenant_session` as a fixture parameter:
  `tenant_session` runs SET LOCAL ROLE test_rls_user on the same underlying
  db_session object BEFORE the test body executes. After the role switch,
  inserting rows whose professional_id != current_tenant is blocked by the
  RLS WITH CHECK clause. We need to create the other tenant's data first
  (as postgres/BYPASSRLS), then switch — so we manage SET LOCAL manually.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from clients.models import Client
from professionals.models import Professional
from reports.repository import ReportsRepository
from tests.reports.conftest import make_session

# ===========================================================================
# find_sessions_in_period
# ===========================================================================


class TestFindSessionsInPeriod:
    # -----------------------------------------------------------------------
    # Date range
    # -----------------------------------------------------------------------

    async def test_returns_sessions_in_date_range(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client,
    ) -> None:
        """Sessions cujo scheduled_at cai dentro do range devem ser retornadas."""
        session = await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        )

        repo = ReportsRepository(tenant_session)
        rows = await repo.find_sessions_in_period(date(2025, 1, 1), date(2025, 1, 31))

        assert len(rows) == 1
        assert rows[0].id == session.id

    async def test_excludes_sessions_outside_date_range(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client,
    ) -> None:
        """Sessions fora do range não devem aparecer no resultado."""
        # Inside range
        inside = await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        )
        # Before start_date
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2024, 12, 31, 23, 59, tzinfo=UTC),
        )
        # After end_date
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 2, 1, 0, 0, tzinfo=UTC),
        )

        repo = ReportsRepository(tenant_session)
        rows = await repo.find_sessions_in_period(date(2025, 1, 1), date(2025, 1, 31))

        assert len(rows) == 1
        assert rows[0].id == inside.id

    # -----------------------------------------------------------------------
    # client_id filter
    # -----------------------------------------------------------------------

    async def test_filters_by_client_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client,
    ) -> None:
        """Quando client_id é fornecido, apenas sessões daquele cliente são retornadas."""
        # Session for test_client
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        )

        # Create a second client for the same professional and add a session
        other_client = Client(
            professional_id=test_professional.id,
            full_name="Other Reports Client",
            phone="11977770002",
        )
        tenant_session.add(other_client)
        await tenant_session.flush()
        await tenant_session.refresh(other_client)

        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=other_client.id,
            scheduled_at=datetime(2025, 1, 16, 10, 0, tzinfo=UTC),
        )

        repo = ReportsRepository(tenant_session)
        rows = await repo.find_sessions_in_period(
            date(2025, 1, 1),
            date(2025, 1, 31),
            client_id=test_client.id,
        )

        assert len(rows) == 1
        assert rows[0].client_id == test_client.id

    # -----------------------------------------------------------------------
    # status filter
    # -----------------------------------------------------------------------

    async def test_filters_by_status(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client,
    ) -> None:
        """Quando status_filter é fornecido, apenas sessões com aquele status são retornadas."""
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
            status="completed",
        )
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 16, 10, 0, tzinfo=UTC),
            status="cancelled",
        )
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 17, 10, 0, tzinfo=UTC),
            status="no_show",
        )

        repo = ReportsRepository(tenant_session)
        rows = await repo.find_sessions_in_period(
            date(2025, 1, 1),
            date(2025, 1, 31),
            status_filter=["completed"],
        )

        assert len(rows) == 1
        assert rows[0].status == "completed"

    async def test_status_filter_accepts_multiple_values(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client,
    ) -> None:
        """status_filter com múltiplos valores retorna sessões de qualquer um deles."""
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
            status="completed",
        )
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 16, 10, 0, tzinfo=UTC),
            status="no_show",
        )
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 17, 10, 0, tzinfo=UTC),
            status="cancelled",
        )

        repo = ReportsRepository(tenant_session)
        rows = await repo.find_sessions_in_period(
            date(2025, 1, 1),
            date(2025, 1, 31),
            status_filter=["completed", "no_show"],
        )

        assert len(rows) == 2
        statuses = {r.status for r in rows}
        assert statuses == {"completed", "no_show"}

    # -----------------------------------------------------------------------
    # Empty result
    # -----------------------------------------------------------------------

    async def test_returns_empty_list_when_no_sessions(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """Sem sessões no período, deve retornar lista vazia."""
        repo = ReportsRepository(tenant_session)
        rows = await repo.find_sessions_in_period(date(2025, 1, 1), date(2025, 1, 31))

        assert rows == []

    # -----------------------------------------------------------------------
    # RLS isolation
    # -----------------------------------------------------------------------

    async def test_rls_other_tenant_sessions_not_visible(
        self,
        db_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        Sessões de outro tenant não devem aparecer mesmo que o UUID seja conhecido.

        Segue o mesmo padrão de TestClientsRepositoryFindById.test_find_by_id_returns_none_for_other_tenant_client:
          1. Cria dados do outro tenant ANTES de mudar de role (postgres tem BYPASSRLS).
          2. Faz SET LOCAL ROLE + SET LOCAL app.current_tenant manualmente.
          3. Consulta — RLS filtra as linhas do outro tenant.

        WHY NOT request `tenant_session` as fixture:
          `tenant_session` aplica SET LOCAL ROLE test_rls_user sobre db_session
          ANTES do corpo do teste. Com o role trocado, INSERT com professional_id
          diferente do current_tenant falha pela cláusula WITH CHECK da policy.
          Por isso gerenciamos o SET LOCAL manualmente neste teste.
        """
        # ── Step 1: create another professional + client + session (postgres, no RLS) ──
        other_prof = Professional(
            email="other_rls_reports@example.com",
            password_hash="h",
            full_name="Other Prof RLS",
        )
        db_session.add(other_prof)
        await db_session.flush()

        other_client = Client(
            professional_id=other_prof.id,
            full_name="Other Tenant Client",
            phone="11000000099",
        )
        db_session.add(other_client)
        await db_session.flush()

        await make_session(
            db_session,
            professional_id=other_prof.id,
            client_id=other_client.id,
            scheduled_at=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        )

        # ── Step 2: activate RLS for test_professional ──
        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))

        # ── Step 3: query — other tenant's sessions must be invisible ──
        repo = ReportsRepository(db_session)
        rows = await repo.find_sessions_in_period(date(2025, 1, 1), date(2025, 1, 31))

        assert len(rows) == 0, "Sessions from another tenant must not be visible via RLS"

    # -----------------------------------------------------------------------
    # JOIN enrichment
    # -----------------------------------------------------------------------

    async def test_row_has_client_name_from_join(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client,
    ) -> None:
        """Cada row deve conter client_name proveniente do JOIN com a tabela clients."""
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
        )

        repo = ReportsRepository(tenant_session)
        rows = await repo.find_sessions_in_period(date(2025, 1, 1), date(2025, 1, 31))

        assert len(rows) == 1
        assert rows[0].client_name == test_client.full_name

    async def test_results_ordered_by_client_id_then_scheduled_at(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client,
    ) -> None:
        """Resultados devem ser ordenados por (client_id, scheduled_at) para agregação eficiente."""
        # Two sessions for test_client, out of chronological order of creation
        s2 = await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 20, 10, 0, tzinfo=UTC),
        )
        s1 = await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 10, 10, 0, tzinfo=UTC),
        )

        repo = ReportsRepository(tenant_session)
        rows = await repo.find_sessions_in_period(date(2025, 1, 1), date(2025, 1, 31))

        assert len(rows) == 2
        # Within the same client, earlier session must come first
        assert rows[0].id == s1.id
        assert rows[1].id == s2.id


# ===========================================================================
# get_period_summary
# ===========================================================================


class TestGetPeriodSummary:
    # -----------------------------------------------------------------------
    # Count and sum
    # -----------------------------------------------------------------------

    async def test_returns_correct_count_and_sum(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client,
    ) -> None:
        """total_sessions e total_amount devem refletir exatamente as sessões do período."""
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
            price=Decimal("150.00"),
        )
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 20, 14, 0, tzinfo=UTC),
            price=Decimal("200.00"),
        )

        repo = ReportsRepository(tenant_session)
        summary = await repo.get_period_summary(date(2025, 1, 1), date(2025, 1, 31))

        assert summary.total_sessions == 2
        assert summary.total_amount == Decimal("350.00")

    # -----------------------------------------------------------------------
    # Coalesce — zero when no sessions
    # -----------------------------------------------------------------------

    async def test_returns_zero_when_no_sessions(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        Sem sessões no período, total_sessions == 0 e total_amount == Decimal('0').

        Verifica que coalesce(sum(price), 0) impede retorno de NULL.
        """
        repo = ReportsRepository(tenant_session)
        summary = await repo.get_period_summary(date(2025, 1, 1), date(2025, 1, 31))

        assert summary.total_sessions == 0
        assert summary.total_amount == Decimal("0")
        assert summary.total_amount is not None

    # -----------------------------------------------------------------------
    # Status filter
    # -----------------------------------------------------------------------

    async def test_filters_by_status(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client,
    ) -> None:
        """get_period_summary deve respeitar status_filter ao calcular count e sum."""
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
            status="completed",
            price=Decimal("150.00"),
        )
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 16, 10, 0, tzinfo=UTC),
            status="cancelled",
            price=Decimal("100.00"),
        )

        repo = ReportsRepository(tenant_session)
        summary = await repo.get_period_summary(
            date(2025, 1, 1),
            date(2025, 1, 31),
            status_filter=["completed"],
        )

        assert summary.total_sessions == 1
        assert summary.total_amount == Decimal("150.00")

    async def test_excludes_sessions_outside_range_from_summary(
        self,
        tenant_session: AsyncSession,
        test_professional,
        test_client,
    ) -> None:
        """Sessões fora do período não devem ser contabilizadas no summary."""
        # Inside range
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 1, 15, 10, 0, tzinfo=UTC),
            price=Decimal("150.00"),
        )
        # Outside range
        await make_session(
            tenant_session,
            professional_id=test_professional.id,
            client_id=test_client.id,
            scheduled_at=datetime(2025, 2, 5, 10, 0, tzinfo=UTC),
            price=Decimal("200.00"),
        )

        repo = ReportsRepository(tenant_session)
        summary = await repo.get_period_summary(date(2025, 1, 1), date(2025, 1, 31))

        assert summary.total_sessions == 1
        assert summary.total_amount == Decimal("150.00")
