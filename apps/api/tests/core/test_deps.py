"""
Tests for core/deps.py — TDD Red phase.

Estes testes definem o contrato das dependências FastAPI:
- get_current_professional_id: extrai e valida o UUID do JWT
- TenantSession: sessão com RLS ativo

Estratégia: criar um mini-app de teste com um endpoint protegido,
então fazer requests com tokens válidos e inválidos.
Não precisa de banco de dados — só valida JWT.
"""

from datetime import UTC, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from core.security import create_access_token

# ---------------------------------------------------------------------------
# Mini-app de teste com um endpoint protegido
# ---------------------------------------------------------------------------

def build_test_app() -> FastAPI:
    """Cria um FastAPI mínimo para testar as dependencies."""
    from core.deps import CurrentProfessionalId

    app = FastAPI()

    @app.get("/protected")
    async def protected_endpoint(prof_id: CurrentProfessionalId) -> dict[str, str]:
        return {"professional_id": prof_id}

    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_app() -> FastAPI:
    return build_test_app()


@pytest.fixture
def valid_professional_id() -> str:
    return "123e4567-e89b-12d3-a456-426614174000"


@pytest.fixture
def valid_token(valid_professional_id: str) -> str:
    return create_access_token(subject=valid_professional_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetCurrentProfessionalId:
    async def test_valid_token_returns_professional_id(
        self,
        test_app: FastAPI,
        valid_token: str,
        valid_professional_id: str,
    ) -> None:
        """Token válido deve extrair o professional_id corretamente."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"  # type: ignore[arg-type]
        ) as client:
            resp = await client.get(
                "/protected", headers={"Authorization": f"Bearer {valid_token}"}
            )

        assert resp.status_code == 200
        assert resp.json()["professional_id"] == valid_professional_id

    async def test_missing_token_returns_401(self, test_app: FastAPI) -> None:
        """Request sem Authorization header deve retornar 401."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"  # type: ignore[arg-type]
        ) as client:
            resp = await client.get("/protected")

        assert resp.status_code == 401

    async def test_malformed_token_returns_401(self, test_app: FastAPI) -> None:
        """Token com formato inválido deve retornar 401, nunca 500."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"  # type: ignore[arg-type]
        ) as client:
            resp = await client.get(
                "/protected", headers={"Authorization": "Bearer not.a.valid.jwt"}
            )

        assert resp.status_code == 401

    async def test_expired_token_returns_401(self, test_app: FastAPI) -> None:
        """Token expirado deve ser rejeitado."""
        expired_token = create_access_token(
            subject="some-uuid", expires_delta=timedelta(seconds=-1)
        )
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"  # type: ignore[arg-type]
        ) as client:
            resp = await client.get(
                "/protected", headers={"Authorization": f"Bearer {expired_token}"}
            )

        assert resp.status_code == 401

    async def test_token_with_wrong_bearer_prefix_returns_401(
        self, test_app: FastAPI, valid_token: str
    ) -> None:
        """Header sem prefixo 'Bearer ' deve retornar 401."""
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"  # type: ignore[arg-type]
        ) as client:
            resp = await client.get(
                "/protected", headers={"Authorization": valid_token}
            )

        assert resp.status_code == 401

    async def test_token_without_sub_claim_returns_401(
        self, test_app: FastAPI
    ) -> None:
        """Token sem campo 'sub' no payload deve retornar 401."""
        from datetime import datetime

        from jose import jwt

        from core.config import settings

        # Token sem 'sub'
        bad_token = jwt.encode(
            {"type": "access", "exp": datetime.now(tz=UTC) + timedelta(hours=1)},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"  # type: ignore[arg-type]
        ) as client:
            resp = await client.get(
                "/protected", headers={"Authorization": f"Bearer {bad_token}"}
            )

        assert resp.status_code == 401
