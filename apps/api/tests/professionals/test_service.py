"""Tests for ProfessionalsService — TDD Red phase.

NOTE: These tests target the *to-be-implemented* RegisterRequest schema
(specialty and bio are optional, phone is not required).
The current schemas.py will be updated as part of the Green phase.
"""

import pytest
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from professionals.service import ProfessionalsService
from professionals.schemas import RegisterRequest, UpdateProfileRequest
from core.exceptions import ConflictError, NotFoundError
from core.security import verify_password


class TestProfessionalsServiceRegister:
    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    async def test_register_creates_professional(
        self, db_session: AsyncSession
    ) -> None:
        """register() deve criar e retornar um Professional com id gerado."""
        service = ProfessionalsService(db_session)

        professional = await service.register(
            RegisterRequest(
                email="reg@example.com",
                password="password123",
                full_name="Reg Test",
            )
        )

        assert professional.id is not None
        assert professional.email == "reg@example.com"
        assert professional.full_name == "Reg Test"

    async def test_register_hashes_password(
        self, db_session: AsyncSession
    ) -> None:
        """register() nunca deve armazenar a senha em plain text."""
        service = ProfessionalsService(db_session)

        professional = await service.register(
            RegisterRequest(
                email="hash@example.com",
                password="password123",
                full_name="Hash Test",
            )
        )

        assert professional.password_hash != "password123"
        assert verify_password("password123", professional.password_hash) is True

    async def test_register_stores_specialty_and_bio(
        self, db_session: AsyncSession
    ) -> None:
        """register() deve persistir specialty e bio quando fornecidos."""
        service = ProfessionalsService(db_session)

        professional = await service.register(
            RegisterRequest(
                email="spec@example.com",
                password="password123",
                full_name="Spec Test",
                specialty="Fisioterapia",
                bio="Especialista em fisioterapia esportiva.",
            )
        )

        assert professional.specialty == "Fisioterapia"
        assert professional.bio == "Especialista em fisioterapia esportiva."

    async def test_register_works_without_specialty_and_bio(
        self, db_session: AsyncSession
    ) -> None:
        """register() deve funcionar com specialty e bio omitidos (campos opcionais)."""
        service = ProfessionalsService(db_session)

        professional = await service.register(
            RegisterRequest(
                email="minimal@example.com",
                password="password123",
                full_name="Minimal Prof",
            )
        )

        assert professional.specialty is None
        assert professional.bio is None

    # ------------------------------------------------------------------
    # Error cases
    # ------------------------------------------------------------------

    async def test_register_raises_conflict_for_duplicate_email(
        self, db_session: AsyncSession
    ) -> None:
        """register() deve lançar ConflictError quando o email já está cadastrado."""
        service = ProfessionalsService(db_session)
        await service.register(
            RegisterRequest(
                email="dup@example.com",
                password="password123",
                full_name="First",
            )
        )

        with pytest.raises(ConflictError):
            await service.register(
                RegisterRequest(
                    email="dup@example.com",
                    password="password456",
                    full_name="Second",
                )
            )


class TestProfessionalsServiceGetById:
    async def test_get_by_id_returns_professional(
        self, db_session: AsyncSession
    ) -> None:
        """get_by_id() deve retornar o professional correto pelo UUID."""
        service = ProfessionalsService(db_session)
        created = await service.register(
            RegisterRequest(
                email="getid@example.com",
                password="password123",
                full_name="Get ID",
            )
        )

        found = await service.get_by_id(created.id)

        assert found.id == created.id
        assert found.email == "getid@example.com"

    async def test_get_by_id_raises_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """get_by_id() deve lançar NotFoundError para UUID inexistente."""
        service = ProfessionalsService(db_session)

        with pytest.raises(NotFoundError):
            await service.get_by_id(uuid4())


class TestProfessionalsServiceUpdateProfile:
    async def test_update_profile_changes_full_name(
        self, db_session: AsyncSession
    ) -> None:
        """update_profile() deve persistir o novo full_name."""
        service = ProfessionalsService(db_session)
        created = await service.register(
            RegisterRequest(
                email="upd@example.com",
                password="password123",
                full_name="Old Name",
            )
        )

        updated = await service.update_profile(
            created.id,
            UpdateProfileRequest(full_name="New Name"),
        )

        assert updated.full_name == "New Name"
        assert updated.id == created.id

    async def test_update_profile_ignores_none_fields(
        self, db_session: AsyncSession
    ) -> None:
        """update_profile() não deve sobrescrever campos existentes quando None
        é passado (campo não incluído na requisição)."""
        service = ProfessionalsService(db_session)
        created = await service.register(
            RegisterRequest(
                email="ignore@example.com",
                password="password123",
                full_name="Ignore None",
                specialty="Yoga",
            )
        )

        # Atualiza apenas bio — specialty deve permanecer inalterado
        updated = await service.update_profile(
            created.id,
            UpdateProfileRequest(bio="Nova bio"),
        )

        assert updated.bio == "Nova bio"
        assert updated.specialty == "Yoga"
