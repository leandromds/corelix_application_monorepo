"""
FastAPI dependencies compartilhadas entre todos os routers.

Dois tipos de sessão:
  DbSession     → sessão pura, sem RLS — rotas públicas (login, registro, webhook)
  TenantSession → sessão + JWT validado + RLS ativo — rotas protegidas

Analogia frontend: DbSession é como um contexto sem autenticação,
TenantSession é o contexto logado com o usuário já resolvido.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db, set_tenant_context
from core.security import decode_access_token

# FastAPI extrai automaticamente o token do header: "Authorization: Bearer <token>"
# tokenUrl aponta para o endpoint de login (usado pelo Swagger UI)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ============================================================================
# JWT — extração e validação
# ============================================================================


async def get_current_professional_id(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> str:
    """
    Extrai o professional_id do JWT.

    Não faz query no banco — só valida a assinatura e decodifica o payload.
    Retorna o 'sub' do token (UUID do profissional como string).

    Levanta 401 para qualquer falha: token ausente, expirado, assinatura
    inválida ou payload incompleto.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
    except JWTError:
        raise credentials_exception

    professional_id: str | None = payload.get("sub")
    if professional_id is None:
        raise credentials_exception

    return professional_id


# ============================================================================
# Session types — os dois building blocks para os routers
# ============================================================================


# Sessão pura — usar em rotas que não exigem autenticação
DbSession = Annotated[AsyncSession, Depends(get_db)]

# Professional ID do JWT — sem query no banco
CurrentProfessionalId = Annotated[str, Depends(get_current_professional_id)]


async def get_tenant_db(
    session: Annotated[AsyncSession, Depends(get_db)],
    professional_id: CurrentProfessionalId,
) -> AsyncSession:
    """
    Sessão com RLS ativo para o tenant autenticado.

    Combina três etapas:
      1. get_db()                     → abre a sessão
      2. get_current_professional_id  → valida JWT, extrai UUID
      3. set_tenant_context()         → executa SET LOCAL no PostgreSQL

    O FastAPI resolve as dependências em cadeia automaticamente.
    Retorna a mesma sessão de get_db() — o lifecycle (commit/rollback/close)
    continua gerenciado por get_db().

    IMPORTANTE: nunca chamar session.commit() no service layer.
    O SET LOCAL é válido apenas na transação corrente — se commitada
    antes do fim do request, o RLS é silenciosamente desativado.
    """
    await set_tenant_context(session, UUID(professional_id))
    return session


# Sessão com RLS — usar na grande maioria dos routers protegidos
TenantSession = Annotated[AsyncSession, Depends(get_tenant_db)]
