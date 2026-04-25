"""
Tests for ClientsRepository — TDD Red phase.

Coverage:
- create()         → with phone only, email only, defaults
- find_by_id()     → found, not found, cross-tenant isolation (RLS)
- find_all()       → active_only filter, skip/limit pagination
- find_by_phone()  → found, not found, cross-tenant isolation (RLS)
- update()         → field change, partial (unset fields preserved)
- soft_delete()    → sets is_active=False, excluded from active list

RLS isolation tests rely on the null-permissive FORCE ROW LEVEL SECURITY
policy applied in conftest.test_engine. The pattern is:
  1. Create data for "other tenant" WITHOUT setting tenant context
     (null-permissive policy allows this).
  2. SET LOCAL app.current_tenant = test_professional.id
  3. Query — RLS filters out the other tenant's rows → returns None / empty.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from clients.models import Client
from clients.repository import ClientsRepository
from clients.schemas import ClientCreate, ClientUpdate
from professionals.models import Professional
from tests.clients.conftest import make_client_create


class TestClientsRepositoryCreate:
    # ------------------------------------------------------------------
    # Happy path — phone only
    # ------------------------------------------------------------------

    async def test_create_with_phone_returns_client_with_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create() deve retornar um Client com id gerado pelo banco (phone only)."""
        repo = ClientsRepository(tenant_session)

        client = await repo.create(
            test_professional.id,
            make_client_create(phone="11999990001"),
        )

        assert client.id is not None
        assert client.full_name == "Test Client"
        assert client.phone == "11999990001"
        assert client.email is None

    # ------------------------------------------------------------------
    # Happy path — email only
    # ------------------------------------------------------------------

    async def test_create_with_email_only_returns_client_with_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create() deve aceitar clientes sem phone, desde que email seja fornecido."""
        repo = ClientsRepository(tenant_session)

        client = await repo.create(
            test_professional.id,
            make_client_create(phone=None, email="emailonly@example.com"),
        )

        assert client.id is not None
        assert client.email == "emailonly@example.com"
        assert client.phone is None

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------

    async def test_create_sets_is_active_true_by_default(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create() deve setar is_active=True por padrão."""
        repo = ClientsRepository(tenant_session)

        client = await repo.create(
            test_professional.id,
            make_client_create(phone="11999990002"),
        )

        assert client.is_active is True

    async def test_create_sets_opt_in_false_by_default(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create() deve setar whatsapp_opt_in e email_opt_in como False por padrão."""
        repo = ClientsRepository(tenant_session)

        client = await repo.create(
            test_professional.id,
            make_client_create(phone="11999990003"),
        )

        assert client.whatsapp_opt_in is False
        assert client.email_opt_in is False

    async def test_create_persists_professional_id(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create() deve vincular o cliente ao professional_id correto."""
        repo = ClientsRepository(tenant_session)

        client = await repo.create(
            test_professional.id,
            make_client_create(phone="11999990004"),
        )

        assert client.professional_id == test_professional.id


class TestClientsRepositoryFindById:
    # ------------------------------------------------------------------
    # Found
    # ------------------------------------------------------------------

    async def test_find_by_id_returns_client(
        self,
        tenant_session: AsyncSession,
        test_client: Client,
    ) -> None:
        """find_by_id() deve retornar o cliente correto pelo UUID."""
        repo = ClientsRepository(tenant_session)

        found = await repo.find_by_id(test_client.id)

        assert found is not None
        assert found.id == test_client.id
        assert found.full_name == test_client.full_name

    # ------------------------------------------------------------------
    # Not found
    # ------------------------------------------------------------------

    async def test_find_by_id_returns_none_when_not_found(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """find_by_id() deve retornar None para UUID inexistente."""
        repo = ClientsRepository(tenant_session)

        result = await repo.find_by_id(uuid4())

        assert result is None

    # ------------------------------------------------------------------
    # RLS isolation
    # ------------------------------------------------------------------

    async def test_find_by_id_returns_none_for_other_tenant_client(
        self,
        db_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        find_by_id() deve retornar None para cliente de outro tenant.

        RLS isola os dados: mesmo conhecendo o UUID, um profissional não pode
        ver dados de outro tenant.
        """
        # Step 1: create prof_b and their client WITHOUT setting tenant context.
        # The null-permissive policy allows inserts with no tenant set.
        prof_b = Professional(
            email="prof_b_repoid@example.com",
            password_hash="h",
            full_name="Prof B",
        )
        db_session.add(prof_b)
        await db_session.flush()

        client_b = Client(
            professional_id=prof_b.id,
            full_name="Client of B",
            phone="11999990099",
        )
        db_session.add(client_b)
        await db_session.flush()

        # Step 2: switch to non-privileged role + activate tenant context.
        # 'postgres' has BYPASSRLS and would ignore all RLS policies.
        # SET LOCAL ROLE test_rls_user (no BYPASSRLS) makes RLS effective.
        # Both SET LOCAL commands are transaction-scoped — reverted on rollback.
        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))

        # Step 3: query — RLS should hide client_b.
        repo = ClientsRepository(db_session)
        result = await repo.find_by_id(client_b.id)

        assert result is None, "Client from another tenant must not be visible via RLS"


class TestClientsRepositoryFindAll:
    # ------------------------------------------------------------------
    # Basic listing
    # ------------------------------------------------------------------

    async def test_find_all_returns_active_clients(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_all() deve retornar clientes ativos do tenant."""
        repo = ClientsRepository(tenant_session)

        c1 = await repo.create(test_professional.id, make_client_create(phone="11999990010"))
        c2 = await repo.create(test_professional.id, make_client_create(phone="11999990011"))

        results = await repo.find_all()

        ids = {c.id for c in results}
        assert c1.id in ids
        assert c2.id in ids

    # ------------------------------------------------------------------
    # active_only filter
    # ------------------------------------------------------------------

    async def test_find_all_excludes_inactive_by_default(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_all() com active_only=True (padrão) não deve retornar clientes inativos."""
        repo = ClientsRepository(tenant_session)

        active = await repo.create(test_professional.id, make_client_create(phone="11999990020"))
        inactive = await repo.create(test_professional.id, make_client_create(phone="11999990021"))
        await repo.soft_delete(inactive)

        results = await repo.find_all()

        ids = {c.id for c in results}
        assert active.id in ids
        assert inactive.id not in ids

    async def test_find_all_includes_inactive_when_active_only_false(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_all(active_only=False) deve retornar todos os clientes."""
        repo = ClientsRepository(tenant_session)

        active = await repo.create(test_professional.id, make_client_create(phone="11999990030"))
        inactive = await repo.create(test_professional.id, make_client_create(phone="11999990031"))
        await repo.soft_delete(inactive)

        results = await repo.find_all(active_only=False)

        ids = {c.id for c in results}
        assert active.id in ids
        assert inactive.id in ids

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    async def test_find_all_respects_limit(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_all(limit=1) deve retornar no máximo 1 cliente."""
        repo = ClientsRepository(tenant_session)

        await repo.create(test_professional.id, make_client_create(phone="11999990040"))
        await repo.create(test_professional.id, make_client_create(phone="11999990041"))

        results = await repo.find_all(limit=1)

        assert len(results) == 1

    async def test_find_all_respects_skip(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_all(skip=N) deve pular os primeiros N registros."""
        repo = ClientsRepository(tenant_session)

        c1 = await repo.create(test_professional.id, make_client_create(phone="11999990050"))
        c2 = await repo.create(test_professional.id, make_client_create(phone="11999990051"))

        all_results = await repo.find_all()
        skipped_results = await repo.find_all(skip=1)

        assert len(skipped_results) == len(all_results) - 1
        # The first result from the full list should not be in the skipped result
        first_id = all_results[0].id
        skipped_ids = {c.id for c in skipped_results}
        assert first_id not in skipped_ids


class TestClientsRepositoryFindByPhone:
    # ------------------------------------------------------------------
    # Found
    # ------------------------------------------------------------------

    async def test_find_by_phone_returns_client(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_by_phone() deve retornar o cliente com o telefone correspondente."""
        repo = ClientsRepository(tenant_session)

        created = await repo.create(test_professional.id, make_client_create(phone="11999990060"))

        found = await repo.find_by_phone("11999990060")

        assert found is not None
        assert found.id == created.id

    # ------------------------------------------------------------------
    # Not found
    # ------------------------------------------------------------------

    async def test_find_by_phone_returns_none_when_not_found(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """find_by_phone() deve retornar None para telefone inexistente."""
        repo = ClientsRepository(tenant_session)

        result = await repo.find_by_phone("00000000000")

        assert result is None

    async def test_find_by_phone_returns_none_for_inactive_client(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """find_by_phone() não deve retornar clientes inativos (soft-deleted)."""
        repo = ClientsRepository(tenant_session)

        client = await repo.create(test_professional.id, make_client_create(phone="11999990065"))
        await repo.soft_delete(client)

        result = await repo.find_by_phone("11999990065")

        assert result is None

    # ------------------------------------------------------------------
    # RLS isolation
    # ------------------------------------------------------------------

    async def test_find_by_phone_returns_none_for_other_tenant(
        self,
        db_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        find_by_phone() deve retornar None para número de outro tenant.

        Isso é a garantia fundamental do sistema: o mesmo telefone pode
        existir em tenants diferentes sem conflito. RLS isola automaticamente.
        """
        # Create prof_b and their client WITHOUT tenant context.
        prof_b = Professional(
            email="prof_b_repophone@example.com",
            password_hash="h",
            full_name="Prof B Phone",
        )
        db_session.add(prof_b)
        await db_session.flush()

        client_b = Client(
            professional_id=prof_b.id,
            full_name="Client of B",
            phone="11999990070",  # same phone as we'll search for
        )
        db_session.add(client_b)
        await db_session.flush()

        # Switch to non-privileged role + activate tenant context.
        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))

        repo = ClientsRepository(db_session)
        result = await repo.find_by_phone("11999990070")

        assert result is None, "Phone from another tenant must not be visible via RLS"


class TestClientsRepositoryUpdate:
    # ------------------------------------------------------------------
    # Field change
    # ------------------------------------------------------------------

    async def test_update_changes_full_name(
        self,
        tenant_session: AsyncSession,
        test_client: Client,
    ) -> None:
        """update() deve persistir o novo valor do campo fornecido."""
        repo = ClientsRepository(tenant_session)

        updated = await repo.update(test_client, {"full_name": "Updated Name"})

        assert updated.full_name == "Updated Name"
        assert updated.id == test_client.id

    async def test_update_does_not_change_unset_fields(
        self,
        tenant_session: AsyncSession,
        test_client: Client,
    ) -> None:
        """update() com dict parcial não deve sobrescrever campos não incluídos."""
        repo = ClientsRepository(tenant_session)
        original_phone = test_client.phone

        await repo.update(test_client, {"full_name": "Name Only Update"})

        # Re-fetch to confirm phone was NOT changed
        refetched = await repo.find_by_id(test_client.id)
        assert refetched is not None
        assert refetched.phone == original_phone

    async def test_update_changes_multiple_fields(
        self,
        tenant_session: AsyncSession,
        test_client: Client,
    ) -> None:
        """update() deve aplicar múltiplos campos em uma única chamada."""
        repo = ClientsRepository(tenant_session)

        updated = await repo.update(
            test_client,
            {"full_name": "Multi Update", "notes": "Some notes", "email_opt_in": True},
        )

        assert updated.full_name == "Multi Update"
        assert updated.notes == "Some notes"
        assert updated.email_opt_in is True


class TestClientsRepositorySoftDelete:
    # ------------------------------------------------------------------
    # Soft delete
    # ------------------------------------------------------------------

    async def test_soft_delete_sets_is_active_false(
        self,
        tenant_session: AsyncSession,
        test_client: Client,
    ) -> None:
        """soft_delete() deve setar is_active=False no cliente."""
        repo = ClientsRepository(tenant_session)

        result = await repo.soft_delete(test_client)

        assert result.is_active is False

    async def test_soft_delete_preserves_record_in_db(
        self,
        tenant_session: AsyncSession,
        test_client: Client,
    ) -> None:
        """
        soft_delete() não deve remover o registro do banco.

        O soft delete é um 'hide from UI' — o dado histórico é preservado
        para relatórios, auditoria e integridade referencial com sessions.
        """
        repo = ClientsRepository(tenant_session)
        client_id = test_client.id

        await repo.soft_delete(test_client)

        # find_all(active_only=False) must still include the record
        all_clients = await repo.find_all(active_only=False)
        ids = {c.id for c in all_clients}
        assert client_id in ids

    async def test_soft_delete_excludes_from_active_list(
        self,
        tenant_session: AsyncSession,
        test_client: Client,
    ) -> None:
        """Após soft_delete, cliente não deve aparecer em find_all() padrão."""
        repo = ClientsRepository(tenant_session)

        await repo.soft_delete(test_client)

        active_clients = await repo.find_all()
        ids = {c.id for c in active_clients}
        assert test_client.id not in ids
