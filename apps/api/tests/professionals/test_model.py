"""Tests for Professional model — TDD Red phase. Requer banco."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from professionals.models import Professional


class TestProfessionalModel:
    async def test_create_professional(self, db_session: AsyncSession) -> None:
        """Deve persistir um professional com os campos obrigatórios."""
        prof = Professional(
            email="maria@example.com",
            password_hash="hashed_password",
            full_name="Maria Silva",
        )
        db_session.add(prof)
        await db_session.flush()

        assert prof.id is not None
        assert prof.is_active is True
        assert prof.session_duration == 60

    async def test_email_must_be_unique(self, db_session: AsyncSession) -> None:
        """Dois profissionais não podem ter o mesmo email."""
        db_session.add(Professional(email="dup@example.com", password_hash="h1", full_name="P1"))
        db_session.add(Professional(email="dup@example.com", password_hash="h2", full_name="P2"))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_email_is_required(self, db_session: AsyncSession) -> None:
        """Email não pode ser nulo."""
        db_session.add(Professional(password_hash="hash", full_name="Sem Email"))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_timestamps_set_automatically(self, db_session: AsyncSession) -> None:
        """created_at e updated_at são definidos pelo banco."""
        prof = Professional(email="ts@example.com", password_hash="h", full_name="TS")
        db_session.add(prof)
        await db_session.flush()
        await db_session.refresh(prof)
        assert prof.created_at is not None
        assert prof.updated_at is not None

    async def test_whatsapp_fields_are_optional(self, db_session: AsyncSession) -> None:
        """Profissional pode ser criado sem WhatsApp conectado."""
        prof = Professional(email="nowpp@example.com", password_hash="h", full_name="No WPP")
        db_session.add(prof)
        await db_session.flush()
        assert prof.whatsapp_phone_id is None
        assert prof.whatsapp_access_token is None
