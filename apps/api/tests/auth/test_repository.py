"""Tests for RefreshTokenRepository — TDD Red phase."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from auth.models import RefreshToken  # noqa: F401
from auth.repository import RefreshTokenRepository
from professionals.models import Professional

# ---------------------------------------------------------------------------
# Module-level helper — NOT a fixture (no decorator)
# ---------------------------------------------------------------------------


async def _make_professional(session: AsyncSession, email: str) -> Professional:
    """Persist a bare Professional row and return it."""
    prof = Professional(email=email, password_hash="hash", full_name="Test")
    session.add(prof)
    await session.flush()
    return prof


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRefreshTokenRepository:
    # ------------------------------------------------------------------
    # create()
    # ------------------------------------------------------------------

    async def test_create_token_persists_record(
        self, db_session: AsyncSession
    ) -> None:
        """create() deve persistir o RefreshToken no banco com os campos fornecidos."""
        prof = await _make_professional(db_session, "persist@example.com")
        repo = RefreshTokenRepository(db_session)
        expires = datetime.now(tz=UTC) + timedelta(days=30)

        token = await repo.create(
            professional_id=prof.id,
            token_hash="abc123hash",
            expires_at=expires,
        )

        assert token.id is not None
        assert token.token_hash == "abc123hash"
        assert token.professional_id == prof.id

    async def test_create_token_defaults_revoked_false(
        self, db_session: AsyncSession
    ) -> None:
        """create() deve criar o token com revoked=False por padrão."""
        prof = await _make_professional(db_session, "revoked_default@example.com")
        repo = RefreshTokenRepository(db_session)
        expires = datetime.now(tz=UTC) + timedelta(days=30)

        token = await repo.create(
            professional_id=prof.id,
            token_hash="default_revoked_hash",
            expires_at=expires,
        )

        assert token.revoked is False

    # ------------------------------------------------------------------
    # find_by_hash()
    # ------------------------------------------------------------------

    async def test_find_by_hash_returns_token(
        self, db_session: AsyncSession
    ) -> None:
        """find_by_hash() deve retornar o token correspondente ao hash."""
        prof = await _make_professional(db_session, "findhash@example.com")
        repo = RefreshTokenRepository(db_session)
        expires = datetime.now(tz=UTC) + timedelta(days=30)
        await repo.create(
            professional_id=prof.id,
            token_hash="findable_hash",
            expires_at=expires,
        )

        found = await repo.find_by_hash("findable_hash")

        assert found is not None
        assert found.token_hash == "findable_hash"

    async def test_find_by_hash_returns_none_when_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """find_by_hash() deve retornar None para hash inexistente."""
        repo = RefreshTokenRepository(db_session)

        result = await repo.find_by_hash("nonexistent_hash")

        assert result is None

    # ------------------------------------------------------------------
    # revoke()
    # ------------------------------------------------------------------

    async def test_revoke_marks_token_revoked(
        self, db_session: AsyncSession
    ) -> None:
        """revoke() deve marcar o token com revoked=True."""
        prof = await _make_professional(db_session, "revoke@example.com")
        repo = RefreshTokenRepository(db_session)
        expires = datetime.now(tz=UTC) + timedelta(days=30)
        await repo.create(
            professional_id=prof.id,
            token_hash="to_be_revoked",
            expires_at=expires,
        )

        await repo.revoke("to_be_revoked")

        token = await repo.find_by_hash("to_be_revoked")
        assert token is not None
        assert token.revoked is True

    # ------------------------------------------------------------------
    # revoke_all()
    # ------------------------------------------------------------------

    async def test_revoke_all_marks_all_tokens_for_professional(
        self, db_session: AsyncSession
    ) -> None:
        """revoke_all() deve revogar todos os tokens de um profissional."""
        prof = await _make_professional(db_session, "revokeall@example.com")
        repo = RefreshTokenRepository(db_session)
        expires = datetime.now(tz=UTC) + timedelta(days=30)
        await repo.create(professional_id=prof.id, token_hash="token_a", expires_at=expires)
        await repo.create(professional_id=prof.id, token_hash="token_b", expires_at=expires)

        await repo.revoke_all(prof.id)

        token_a = await repo.find_by_hash("token_a")
        token_b = await repo.find_by_hash("token_b")
        assert token_a is not None and token_a.revoked is True
        assert token_b is not None and token_b.revoked is True

    async def test_revoke_all_does_not_affect_other_professionals(
        self, db_session: AsyncSession
    ) -> None:
        """revoke_all() não deve afetar tokens de outros profissionais."""
        prof_a = await _make_professional(db_session, "prof_a@example.com")
        prof_b = await _make_professional(db_session, "prof_b@example.com")
        repo = RefreshTokenRepository(db_session)
        expires = datetime.now(tz=UTC) + timedelta(days=30)
        await repo.create(professional_id=prof_a.id, token_hash="a_token", expires_at=expires)
        await repo.create(professional_id=prof_b.id, token_hash="b_token", expires_at=expires)

        await repo.revoke_all(prof_a.id)

        token_b = await repo.find_by_hash("b_token")
        assert token_b is not None
        assert token_b.revoked is False

    # ------------------------------------------------------------------
    # delete_expired()
    # ------------------------------------------------------------------

    async def test_delete_expired_removes_past_tokens_and_returns_count(
        self, db_session: AsyncSession
    ) -> None:
        """delete_expired() deve remover tokens vencidos e retornar a contagem."""
        prof = await _make_professional(db_session, "expired@example.com")
        repo = RefreshTokenRepository(db_session)
        past = datetime.now(tz=UTC) - timedelta(seconds=1)
        await repo.create(professional_id=prof.id, token_hash="expired_a", expires_at=past)
        await repo.create(professional_id=prof.id, token_hash="expired_b", expires_at=past)

        count = await repo.delete_expired()

        assert count == 2
        assert await repo.find_by_hash("expired_a") is None
        assert await repo.find_by_hash("expired_b") is None

    async def test_delete_expired_keeps_future_tokens(
        self, db_session: AsyncSession
    ) -> None:
        """delete_expired() não deve remover tokens ainda válidos."""
        prof = await _make_professional(db_session, "future@example.com")
        repo = RefreshTokenRepository(db_session)
        future = datetime.now(tz=UTC) + timedelta(days=30)
        await repo.create(professional_id=prof.id, token_hash="future_token", expires_at=future)

        count = await repo.delete_expired()

        assert count == 0
        assert await repo.find_by_hash("future_token") is not None
