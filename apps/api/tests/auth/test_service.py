"""Tests for AuthService — TDD Red phase."""

import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from auth.service import AuthService
from auth.repository import RefreshTokenRepository
from professionals.service import ProfessionalsService
from professionals.schemas import RegisterRequest
from core.exceptions import AuthenticationError
from core.security import decode_access_token, generate_refresh_token, hash_refresh_token


# ---------------------------------------------------------------------------
# Module-level helper — NOT a fixture
# ---------------------------------------------------------------------------


async def _register(
    session: AsyncSession,
    email: str = "prof@example.com",
):
    """Register a professional and return the model."""
    service = ProfessionalsService(session)
    return await service.register(
        RegisterRequest(email=email, password="password123", full_name="Test Prof")
    )


# ---------------------------------------------------------------------------
# login()
# ---------------------------------------------------------------------------


class TestAuthServiceLogin:
    async def test_login_returns_access_and_refresh_token(
        self, db_session: AsyncSession
    ) -> None:
        """login() deve retornar um dict com access_token e refresh_token."""
        await _register(db_session)
        auth = AuthService(db_session)

        tokens = await auth.login(email="prof@example.com", password="password123")

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["access_token"]
        assert tokens["refresh_token"]

    async def test_login_access_token_contains_correct_sub(
        self, db_session: AsyncSession
    ) -> None:
        """O campo sub do access_token deve conter o id do profissional autenticado."""
        professional = await _register(db_session, email="sub@example.com")
        auth = AuthService(db_session)

        tokens = await auth.login(email="sub@example.com", password="password123")

        payload = decode_access_token(tokens["access_token"])
        assert payload["sub"] == str(professional.id)

    async def test_login_raises_for_wrong_email(
        self, db_session: AsyncSession
    ) -> None:
        """login() deve lançar AuthenticationError quando o email não existe."""
        auth = AuthService(db_session)

        with pytest.raises(AuthenticationError):
            await auth.login(email="ghost@example.com", password="password123")

    async def test_login_raises_for_wrong_password(
        self, db_session: AsyncSession
    ) -> None:
        """login() deve lançar AuthenticationError para senha incorreta."""
        await _register(db_session)
        auth = AuthService(db_session)

        with pytest.raises(AuthenticationError):
            await auth.login(email="prof@example.com", password="wrongpassword")

    async def test_login_with_device_info_stores_it(
        self, db_session: AsyncSession
    ) -> None:
        """login() com device_info deve persistir o valor no registro do token."""
        await _register(db_session, email="device@example.com")
        auth = AuthService(db_session)

        tokens = await auth.login(
            email="device@example.com",
            password="password123",
            device_info="iPhone 15",
        )

        # Recupera o token pelo hash do raw token retornado
        stored_hash = hash_refresh_token(tokens["refresh_token"])
        repo = RefreshTokenRepository(db_session)
        stored_token = await repo.find_by_hash(stored_hash)

        assert stored_token is not None
        assert stored_token.device_info == "iPhone 15"


# ---------------------------------------------------------------------------
# refresh_access_token()
# ---------------------------------------------------------------------------


class TestAuthServiceRefresh:
    async def test_refresh_returns_new_access_token(
        self, db_session: AsyncSession
    ) -> None:
        """refresh_access_token() deve retornar um dict com access_token."""
        await _register(db_session)
        auth = AuthService(db_session)
        tokens = await auth.login(email="prof@example.com", password="password123")

        result = await auth.refresh_access_token(tokens["refresh_token"])

        assert "access_token" in result
        assert result["access_token"]

    async def test_refresh_access_token_has_valid_jwt(
        self, db_session: AsyncSession
    ) -> None:
        """O access_token retornado pelo refresh deve ser um JWT válido e decodificável."""
        await _register(db_session)
        auth = AuthService(db_session)
        tokens = await auth.login(email="prof@example.com", password="password123")

        result = await auth.refresh_access_token(tokens["refresh_token"])

        payload = decode_access_token(result["access_token"])
        assert "sub" in payload
        assert payload.get("type") == "access"

    async def test_refresh_raises_for_revoked_token(
        self, db_session: AsyncSession
    ) -> None:
        """refresh_access_token() deve lançar AuthenticationError para token revogado."""
        await _register(db_session)
        auth = AuthService(db_session)
        tokens = await auth.login(email="prof@example.com", password="password123")
        await auth.logout(tokens["refresh_token"])

        with pytest.raises(AuthenticationError):
            await auth.refresh_access_token(tokens["refresh_token"])

    async def test_refresh_raises_for_expired_token(
        self, db_session: AsyncSession
    ) -> None:
        """refresh_access_token() deve lançar AuthenticationError para token expirado."""
        professional = await _register(db_session)
        raw_token, token_hash = generate_refresh_token()
        repo = RefreshTokenRepository(db_session)
        # Insere diretamente com expires_at no passado
        await repo.create(
            professional_id=professional.id,
            token_hash=token_hash,
            expires_at=datetime.now(tz=timezone.utc) - timedelta(seconds=1),
        )
        auth = AuthService(db_session)

        with pytest.raises(AuthenticationError):
            await auth.refresh_access_token(raw_token)

    async def test_refresh_raises_for_nonexistent_token(
        self, db_session: AsyncSession
    ) -> None:
        """refresh_access_token() deve lançar AuthenticationError para token inexistente."""
        auth = AuthService(db_session)
        raw_token, _ = generate_refresh_token()

        with pytest.raises(AuthenticationError):
            await auth.refresh_access_token(raw_token)


# ---------------------------------------------------------------------------
# logout() / logout_all()
# ---------------------------------------------------------------------------


class TestAuthServiceLogout:
    async def test_logout_revokes_token(
        self, db_session: AsyncSession
    ) -> None:
        """logout() deve marcar o refresh token como revogado no banco."""
        await _register(db_session)
        auth = AuthService(db_session)
        tokens = await auth.login(email="prof@example.com", password="password123")

        await auth.logout(tokens["refresh_token"])

        stored_hash = hash_refresh_token(tokens["refresh_token"])
        repo = RefreshTokenRepository(db_session)
        stored = await repo.find_by_hash(stored_hash)
        assert stored is not None
        assert stored.revoked is True

    async def test_logout_after_revoke_raises_on_refresh(
        self, db_session: AsyncSession
    ) -> None:
        """Tentar refresh após logout deve lançar AuthenticationError."""
        await _register(db_session)
        auth = AuthService(db_session)
        tokens = await auth.login(email="prof@example.com", password="password123")
        await auth.logout(tokens["refresh_token"])

        with pytest.raises(AuthenticationError):
            await auth.refresh_access_token(tokens["refresh_token"])

    async def test_logout_all_revokes_all_tokens(
        self, db_session: AsyncSession
    ) -> None:
        """logout_all() deve marcar todos os tokens do profissional como revogados."""
        professional = await _register(db_session)
        auth = AuthService(db_session)
        tokens_a = await auth.login(email="prof@example.com", password="password123")
        tokens_b = await auth.login(email="prof@example.com", password="password123")

        await auth.logout_all(professional.id)

        repo = RefreshTokenRepository(db_session)
        stored_a = await repo.find_by_hash(hash_refresh_token(tokens_a["refresh_token"]))
        stored_b = await repo.find_by_hash(hash_refresh_token(tokens_b["refresh_token"]))
        assert stored_a is not None and stored_a.revoked is True
        assert stored_b is not None and stored_b.revoked is True

    async def test_logout_all_prevents_all_refreshes(
        self, db_session: AsyncSession
    ) -> None:
        """Após logout_all, nenhum refresh token deve ser utilizável."""
        professional = await _register(db_session)
        auth = AuthService(db_session)
        tokens_a = await auth.login(email="prof@example.com", password="password123")
        tokens_b = await auth.login(email="prof@example.com", password="password123")

        await auth.logout_all(professional.id)

        with pytest.raises(AuthenticationError):
            await auth.refresh_access_token(tokens_a["refresh_token"])

        with pytest.raises(AuthenticationError):
            await auth.refresh_access_token(tokens_b["refresh_token"])
