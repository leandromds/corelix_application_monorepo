"""Tests for ProfessionalsRepository — TDD Red phase."""

import pytest
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from professionals.repository import ProfessionalsRepository
from core.exceptions import NotFoundError


class TestProfessionalsRepository:
    # ------------------------------------------------------------------
    # create()
    # ------------------------------------------------------------------

    async def test_create_returns_professional_with_id(
        self, db_session: AsyncSession
    ) -> None:
        """create() deve retornar um Professional com id gerado pelo banco."""
        repo = ProfessionalsRepository(db_session)

        professional = await repo.create(
            {
                "email": "create@example.com",
                "password_hash": "hashed_pw",
                "full_name": "Create Test",
            }
        )

        assert professional.id is not None
        assert professional.email == "create@example.com"
        assert professional.full_name == "Create Test"

    async def test_create_sets_default_is_active_true(
        self, db_session: AsyncSession
    ) -> None:
        """create() sem is_active deve usar o default True do modelo."""
        repo = ProfessionalsRepository(db_session)

        professional = await repo.create(
            {
                "email": "active@example.com",
                "password_hash": "hashed_pw",
                "full_name": "Active Test",
            }
        )

        assert professional.is_active is True

    # ------------------------------------------------------------------
    # find_by_email()
    # ------------------------------------------------------------------

    async def test_find_by_email_returns_professional(
        self, db_session: AsyncSession
    ) -> None:
        """find_by_email() deve retornar o professional correspondente ao email."""
        repo = ProfessionalsRepository(db_session)
        await repo.create(
            {"email": "find@example.com", "password_hash": "h", "full_name": "Find Me"}
        )

        found = await repo.find_by_email("find@example.com")

        assert found is not None
        assert found.email == "find@example.com"

    async def test_find_by_email_returns_none_when_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """find_by_email() deve retornar None para email inexistente."""
        repo = ProfessionalsRepository(db_session)

        result = await repo.find_by_email("ghost@example.com")

        assert result is None

    # ------------------------------------------------------------------
    # find_by_id()
    # ------------------------------------------------------------------

    async def test_find_by_id_returns_professional(
        self, db_session: AsyncSession
    ) -> None:
        """find_by_id() deve retornar o professional pelo UUID correto."""
        repo = ProfessionalsRepository(db_session)
        created = await repo.create(
            {"email": "byid@example.com", "password_hash": "h", "full_name": "By ID"}
        )

        found = await repo.find_by_id(created.id)

        assert found is not None
        assert found.id == created.id
        assert found.email == "byid@example.com"

    async def test_find_by_id_returns_none_when_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """find_by_id() deve retornar None para UUID inexistente."""
        repo = ProfessionalsRepository(db_session)

        result = await repo.find_by_id(uuid4())

        assert result is None

    # ------------------------------------------------------------------
    # update()
    # ------------------------------------------------------------------

    async def test_update_changes_field(
        self, db_session: AsyncSession
    ) -> None:
        """update() deve persistir o novo valor do campo fornecido."""
        repo = ProfessionalsRepository(db_session)
        created = await repo.create(
            {
                "email": "upd@example.com",
                "password_hash": "h",
                "full_name": "Before Update",
            }
        )

        updated = await repo.update(created.id, {"full_name": "After Update"})

        assert updated.full_name == "After Update"
        assert updated.id == created.id

    async def test_update_raises_not_found_for_unknown_id(
        self, db_session: AsyncSession
    ) -> None:
        """update() deve lançar NotFoundError para UUID inexistente."""
        repo = ProfessionalsRepository(db_session)

        with pytest.raises(NotFoundError):
            await repo.update(uuid4(), {"full_name": "Ghost"})
