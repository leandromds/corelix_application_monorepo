"""Tests for Client model + RLS isolation — TDD Red phase. Requer banco."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import uuid as _uuid

from clients.models import Client
from professionals.models import Professional


async def _make_prof(session: AsyncSession, email: str) -> Professional:
    p = Professional(email=email, password_hash="h", full_name="Test")
    session.add(p)
    await session.flush()
    return p


class TestClientModel:
    async def test_create_client(self, db_session: AsyncSession) -> None:
        """Deve persistir cliente vinculado a um profissional."""
        prof = await _make_prof(db_session, "prof_client@example.com")
        client = Client(professional_id=prof.id, full_name="João Cliente", phone="11999998888")
        db_session.add(client)
        await db_session.flush()
        assert client.id is not None
        assert client.whatsapp_opt_in is False
        assert client.is_active is True

    async def test_client_requires_valid_professional(self, db_session: AsyncSession) -> None:
        """FK RESTRICT: professional_id inválido deve falhar."""
        db_session.add(Client(professional_id=_uuid.uuid4(), full_name="Orphan"))
        with pytest.raises(IntegrityError):
            await db_session.flush()


class TestClientRLS:
    """Valida o isolamento multi-tenant via RLS do PostgreSQL."""

    async def test_rls_isolates_clients_between_tenants(
        self, db_session: AsyncSession
    ) -> None:
        """Profissional A não deve ver clientes do Profissional B."""
        prof_a = await _make_prof(db_session, "prof_a_rls@example.com")
        prof_b = await _make_prof(db_session, "prof_b_rls@example.com")

        client_a = Client(professional_id=prof_a.id, full_name="Cliente de A")
        client_b = Client(professional_id=prof_b.id, full_name="Cliente de B")
        db_session.add_all([client_a, client_b])
        await db_session.flush()

        # Ativa contexto para o profissional A
        await db_session.execute(
            text("SET LOCAL app.current_tenant = :id"), {"id": str(prof_a.id)}
        )

        result = await db_session.execute(select(Client))
        visible_ids = {c.id for c in result.scalars().all()}

        assert client_a.id in visible_ids, "Cliente A deve ser visível para prof A"
        assert client_b.id not in visible_ids, "Cliente B NÃO deve ser visível para prof A"
