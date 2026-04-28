"""
Tests for ClientsService — TDD Red phase.

Coverage:
- create_client()   → phone only, email only, duplicate phone (ConflictError),
                      same phone different tenant (allowed via RLS)
- get_client()      → found, not found (NotFoundError), cross-tenant (NotFoundError via RLS)
- list_clients()    → returns active, excludes soft-deleted
- update_client()   → field change, partial PATCH semantics, not found
- delete_client()   → soft delete, excluded from list, not found

RLS cross-tenant tests follow the null-permissive pattern:
  1. Create "other tenant" data WITHOUT setting tenant context.
  2. SET LOCAL app.current_tenant = test_professional.id
  3. Call service — RLS filters out other tenant's rows → NotFoundError / no conflict.

IMPORTANT: Service tests use `tenant_session` (defined in tests/clients/conftest.py)
so that RLS is active for all SELECT queries.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from clients.models import Client
from clients.schemas import ClientCreate, ClientUpdate
from clients.service import ClientsService
from core.exceptions import ConflictError, NotFoundError
from professionals.models import Professional
from tests.clients.conftest import make_client_create


class TestClientsServiceCreate:
    # ------------------------------------------------------------------
    # Happy path — phone only
    # ------------------------------------------------------------------

    async def test_create_client_with_phone_returns_client(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create_client() deve retornar Client persistido com phone apenas."""
        service = ClientsService(tenant_session)

        client = await service.create_client(
            test_professional.id,
            make_client_create(phone="11999990100"),
        )

        assert client.id is not None
        assert client.phone == "11999990100"
        assert client.email is None
        assert client.professional_id == test_professional.id

    # ------------------------------------------------------------------
    # Happy path — email only
    # ------------------------------------------------------------------

    async def test_create_client_with_email_only_returns_client(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """create_client() deve aceitar clients sem phone, desde que email seja fornecido."""
        service = ClientsService(tenant_session)

        client = await service.create_client(
            test_professional.id,
            make_client_create(phone=None, email="emailonly_svc@example.com"),
        )

        assert client.id is not None
        assert client.email == "emailonly_svc@example.com"
        assert client.phone is None

    # ------------------------------------------------------------------
    # Duplicate phone — same tenant
    # ------------------------------------------------------------------

    async def test_create_raises_conflict_for_duplicate_phone_same_tenant(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        create_client() deve lançar ConflictError para phone duplicado no mesmo tenant.

        RLS garante que find_by_phone busca apenas no tenant ativo, então
        o ConflictError é sempre relativo ao tenant corrente.
        """
        service = ClientsService(tenant_session)

        await service.create_client(
            test_professional.id,
            make_client_create(phone="11999990110"),
        )

        with pytest.raises(ConflictError):
            await service.create_client(
                test_professional.id,
                make_client_create(
                    full_name="Different Client",
                    phone="11999990110",  # same phone
                ),
            )

    # ------------------------------------------------------------------
    # Duplicate phone — different tenant (RLS isolation)
    # ------------------------------------------------------------------

    async def test_create_allows_duplicate_phone_different_tenant(
        self,
        db_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        O mesmo telefone em tenants diferentes deve ser permitido.

        find_by_phone() é filtrado por RLS ao tenant ativo, portanto o
        número de outro profissional não é visível e não gera ConflictError.
        """
        # Create prof_b and their client WITHOUT tenant context.
        prof_b = Professional(
            email="prof_b_svccreate@example.com",
            password_hash="h",
            full_name="Prof B",
        )
        db_session.add(prof_b)
        await db_session.flush()

        client_b = Client(
            professional_id=prof_b.id,
            full_name="Client of B",
            phone="11999990120",
        )
        db_session.add(client_b)
        await db_session.flush()

        # Switch to non-privileged role + activate tenant context.
        # 'postgres' has BYPASSRLS and would ignore all RLS policies.
        # SET LOCAL ROLE test_rls_user (no BYPASSRLS) makes RLS effective.
        # Both SET LOCAL commands are transaction-scoped — reverted on rollback.
        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))

        # Creating with the same phone should NOT raise ConflictError.
        service = ClientsService(db_session)
        client_a = await service.create_client(
            test_professional.id,
            make_client_create(
                full_name="Client of A",
                phone="11999990120",  # same phone as client_b
            ),
        )

        assert client_a.id is not None
        assert client_a.phone == "11999990120"

    # ------------------------------------------------------------------
    # Schema-level validation (passed through to service)
    # ------------------------------------------------------------------

    async def test_create_raises_validation_error_without_contact(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        create_client() com phone=None e email=None deve falhar na validação do schema.

        A validação ocorre no Pydantic (ClientCreate.model_validator), antes de
        chegar à camada de serviço. Testamos aqui que o schema rejeita a entrada,
        não que o service trata o caso — defense in depth.
        """
        with pytest.raises(ValueError, match="At least one contact method"):
            ClientCreate(full_name="No Contact", phone=None, email=None)


class TestClientsServiceGetClient:
    # ------------------------------------------------------------------
    # Found
    # ------------------------------------------------------------------

    async def test_get_client_returns_client(
        self,
        tenant_session: AsyncSession,
        test_client: Client,
    ) -> None:
        """get_client() deve retornar o cliente correto pelo UUID."""
        service = ClientsService(tenant_session)

        found = await service.get_client(test_client.id)

        assert found.id == test_client.id
        assert found.full_name == test_client.full_name

    # ------------------------------------------------------------------
    # Not found
    # ------------------------------------------------------------------

    async def test_get_client_raises_not_found_for_unknown_id(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """get_client() deve lançar NotFoundError para UUID inexistente."""
        service = ClientsService(tenant_session)

        with pytest.raises(NotFoundError):
            await service.get_client(uuid4())

    # ------------------------------------------------------------------
    # Cross-tenant isolation (RLS)
    # ------------------------------------------------------------------

    async def test_get_client_raises_not_found_for_other_tenant_client(
        self,
        db_session: AsyncSession,
        test_professional,
    ) -> None:
        """
        get_client() deve lançar NotFoundError para cliente de outro tenant.

        RLS torna o cliente de outro tenant invisível, o que se manifesta
        como NotFoundError — não como 403 (AuthorizationError). Isso evita
        que o chamador saiba se o recurso existe em outro tenant.
        """
        # Create prof_b and their client WITHOUT tenant context.
        prof_b = Professional(
            email="prof_b_svcget@example.com",
            password_hash="h",
            full_name="Prof B",
        )
        db_session.add(prof_b)
        await db_session.flush()

        client_b = Client(
            professional_id=prof_b.id,
            full_name="Client of B",
            phone="11999990130",
        )
        db_session.add(client_b)
        await db_session.flush()

        # Switch to non-privileged role + activate tenant context.
        await db_session.execute(text("SET LOCAL ROLE test_rls_user"))
        await db_session.execute(text(f"SET LOCAL app.current_tenant = '{test_professional.id}'"))

        service = ClientsService(db_session)
        with pytest.raises(NotFoundError):
            await service.get_client(client_b.id)


class TestClientsServiceListClients:
    # ------------------------------------------------------------------
    # Basic listing
    # ------------------------------------------------------------------

    async def test_list_clients_returns_active_clients(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """list_clients() deve retornar os clientes ativos do tenant."""
        service = ClientsService(tenant_session)

        c1 = await service.create_client(
            test_professional.id, make_client_create(phone="11999990140")
        )
        c2 = await service.create_client(
            test_professional.id, make_client_create(phone="11999990141")
        )

        results = await service.list_clients()

        ids = {c.id for c in results}
        assert c1.id in ids
        assert c2.id in ids

    async def test_list_clients_excludes_soft_deleted(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """list_clients() não deve retornar clientes que foram soft-deleted."""
        service = ClientsService(tenant_session)

        active = await service.create_client(
            test_professional.id, make_client_create(phone="11999990150")
        )
        to_delete = await service.create_client(
            test_professional.id, make_client_create(phone="11999990151")
        )
        await service.delete_client(to_delete.id)

        results = await service.list_clients()

        ids = {c.id for c in results}
        assert active.id in ids
        assert to_delete.id not in ids

    async def test_list_clients_returns_empty_when_no_clients(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """list_clients() deve retornar lista vazia quando não há clientes."""
        service = ClientsService(tenant_session)

        results = await service.list_clients()

        assert results == []

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    async def test_list_clients_respects_limit(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """list_clients(limit=1) deve retornar no máximo 1 cliente."""
        service = ClientsService(tenant_session)

        await service.create_client(test_professional.id, make_client_create(phone="11999990160"))
        await service.create_client(test_professional.id, make_client_create(phone="11999990161"))

        results = await service.list_clients(limit=1)

        assert len(results) == 1

    async def test_list_clients_respects_skip(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """list_clients(skip=1) deve pular o primeiro registro."""
        service = ClientsService(tenant_session)

        await service.create_client(test_professional.id, make_client_create(phone="11999990170"))
        await service.create_client(test_professional.id, make_client_create(phone="11999990171"))

        all_results = await service.list_clients()
        skipped = await service.list_clients(skip=1)

        assert len(skipped) == len(all_results) - 1


class TestClientsServiceUpdateClient:
    # ------------------------------------------------------------------
    # Field change
    # ------------------------------------------------------------------

    async def test_update_client_changes_full_name(
        self,
        tenant_session: AsyncSession,
        test_client: Client,
    ) -> None:
        """update_client() deve persistir o novo full_name."""
        service = ClientsService(tenant_session)

        updated = await service.update_client(
            test_client.id,
            ClientUpdate(full_name="Updated Name"),
        )

        assert updated.full_name == "Updated Name"
        assert updated.id == test_client.id

    # ------------------------------------------------------------------
    # PATCH semantics — unset fields preserved
    # ------------------------------------------------------------------

    async def test_update_client_partial_does_not_clear_other_fields(
        self,
        tenant_session: AsyncSession,
        test_client: Client,
    ) -> None:
        """
        update_client() com ClientUpdate parcial não deve apagar campos não enviados.

        Isso valida a semântica de PATCH: o frontend pode enviar apenas
        {"full_name": "Novo Nome"} e phone, email, notes permanecem inalterados.
        O service usa model_dump(exclude_unset=True) para isso.
        """
        service = ClientsService(tenant_session)
        original_phone = test_client.phone

        updated = await service.update_client(
            test_client.id,
            ClientUpdate(full_name="Partial Update"),
        )

        assert updated.full_name == "Partial Update"
        assert updated.phone == original_phone  # untouched

    async def test_update_client_changes_notes(
        self,
        tenant_session: AsyncSession,
        test_client: Client,
    ) -> None:
        """update_client() deve persistir alteração em notes."""
        service = ClientsService(tenant_session)

        updated = await service.update_client(
            test_client.id,
            ClientUpdate(notes="Updated notes"),
        )

        assert updated.notes == "Updated notes"

    async def test_update_client_updates_opt_in_flags(
        self,
        tenant_session: AsyncSession,
        test_client: Client,
    ) -> None:
        """update_client() deve atualizar flags de opt-in."""
        service = ClientsService(tenant_session)

        updated = await service.update_client(
            test_client.id,
            ClientUpdate(whatsapp_opt_in=True, email_opt_in=True),
        )

        assert updated.whatsapp_opt_in is True
        assert updated.email_opt_in is True

    # ------------------------------------------------------------------
    # Not found
    # ------------------------------------------------------------------

    async def test_update_client_raises_not_found_for_unknown_id(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """update_client() deve lançar NotFoundError para UUID inexistente."""
        service = ClientsService(tenant_session)

        with pytest.raises(NotFoundError):
            await service.update_client(
                uuid4(),
                ClientUpdate(full_name="Ghost"),
            )


class TestClientsServiceDeleteClient:
    # ------------------------------------------------------------------
    # Soft delete
    # ------------------------------------------------------------------

    async def test_delete_client_soft_deletes(
        self,
        tenant_session: AsyncSession,
        test_client: Client,
    ) -> None:
        """
        delete_client() deve fazer soft delete (is_active=False).

        O registro persiste no banco para preservar histórico. O cliente
        apenas deixa de aparecer nas listagens ativas.
        """
        service = ClientsService(tenant_session)

        await service.delete_client(test_client.id)

        # Fetch with active_only=False to confirm the record still exists.
        from clients.repository import ClientsRepository

        repo = ClientsRepository(tenant_session)
        all_clients = await repo.find_all(active_only=False)
        ids = {c.id for c in all_clients}
        assert test_client.id in ids

    async def test_delete_client_excluded_from_active_list(
        self,
        tenant_session: AsyncSession,
        test_professional,
    ) -> None:
        """Após delete_client(), o cliente não deve aparecer em list_clients()."""
        service = ClientsService(tenant_session)

        client = await service.create_client(
            test_professional.id,
            make_client_create(phone="11999990180"),
        )

        await service.delete_client(client.id)

        results = await service.list_clients()
        ids = {c.id for c in results}
        assert client.id not in ids

    async def test_delete_client_returns_none(
        self,
        tenant_session: AsyncSession,
        test_client: Client,
    ) -> None:
        """delete_client() deve retornar None (sem body na resposta HTTP 204)."""
        service = ClientsService(tenant_session)

        result = await service.delete_client(test_client.id)  # type: ignore[func-returns-value]

        assert result is None

    # ------------------------------------------------------------------
    # Not found
    # ------------------------------------------------------------------

    async def test_delete_client_raises_not_found_for_unknown_id(
        self,
        tenant_session: AsyncSession,
    ) -> None:
        """delete_client() deve lançar NotFoundError para UUID inexistente."""
        service = ClientsService(tenant_session)

        with pytest.raises(NotFoundError):
            await service.delete_client(uuid4())
