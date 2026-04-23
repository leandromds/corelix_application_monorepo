"""
Core module for Secretária Digital API.

This module provides:
- Configuration (settings)
- Database engine and session management
- Custom exceptions
- Security utilities (to be implemented)
"""

from core.config import settings
from core.database import (
    Base,
    async_session_maker,
    check_database_connection,
    clear_tenant_context,
    close_db,
    engine,
    get_db,
    init_db,
    set_tenant_context,
)
from core.exceptions import (
    AppException,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DatabaseError,
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

__all__ = [
    # Config
    "settings",
    # Database
    "Base",
    "engine",
    "async_session_maker",
    "get_db",
    "set_tenant_context",
    "clear_tenant_context",
    "init_db",
    "close_db",
    "check_database_connection",
    # Exceptions
    "AppException",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ValidationError",
    "ConflictError",
    "ExternalServiceError",
    "RateLimitError",
    "DatabaseError",
]
