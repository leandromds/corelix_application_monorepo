"""Tests for RefreshToken model — TDD Red phase. Requer banco."""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models import RefreshToken
from professionals.models import Professional


async def _make_prof(session: AsyncSession, email: str) -> Professional:
    p = Professional(email=email, password_hash="h", full_name="Test")
    session.add(p)
    await session.flush()
    return p


class TestRefreshTokenModel:
    async def test_create_refresh_token(self, db_session: AsyncSession) -> None:
        """Deve persistir refresh token vinculado a um profissional."""
        prof = await _make_prof(db_session, "token_owner@example.com")
        token = RefreshToken(
            professional_id=prof.id,
            token_hash="abc123hash",
            expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
        )
        db_session.add(token)
        await db_session.flush()
        assert token.id is not None
        assert token.revoked is False
        assert token.created_at is not None

    async def test_token_hash_must_be_unique(self, db_session: AsyncSession) -> None:
        """Hash duplicado deve falhar com IntegrityError."""
        prof = await _make_prof(db_session, "uniq_hash@example.com")
        expires = datetime.now(tz=timezone.utc) + timedelta(days=30)
        db_session.add(RefreshToken(professional_id=prof.id, token_hash="dup", expires_at=expires))
        db_session.add(RefreshToken(professional_id=prof.id, token_hash="dup", expires_at=expires))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    def test_refresh_token_has_no_updated_at(self) -> None:
        """RefreshToken usa CreatedAtMixin — não deve ter updated_at."""
        assert not hasattr(RefreshToken, "updated_at")
