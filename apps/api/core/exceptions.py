"""
Custom application exceptions.

These exceptions are caught by the FastAPI exception handler
and converted to appropriate HTTP responses.
"""

from typing import Any


class AppException(Exception):
    """
    Base exception for all application-specific errors.

    All custom exceptions should inherit from this class.
    This allows for centralized exception handling in FastAPI.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
        super().__init__(self.message)


class AuthenticationError(AppException):
    """
    Raised when authentication fails.

    Examples:
    - Invalid credentials
    - Expired token
    - Missing authentication header
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, status_code=401, detail=detail)


class AuthorizationError(AppException):
    """
    Raised when user is authenticated but not authorized for the action.

    Examples:
    - Accessing another tenant's data
    - Insufficient permissions
    """

    def __init__(
        self,
        message: str = "Not authorized to perform this action",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, status_code=403, detail=detail)


class NotFoundError(AppException):
    """
    Raised when a requested resource is not found.

    Examples:
    - Client not found
    - Session not found
    - Professional not found
    """

    def __init__(
        self,
        message: str = "Resource not found",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, status_code=404, detail=detail)


class ValidationError(AppException):
    """
    Raised when business logic validation fails.

    Note: This is different from Pydantic's ValidationError,
    which handles input validation at the HTTP layer.
    This is for business rules (e.g., overlapping sessions).

    Examples:
    - Session time conflicts with existing session
    - Cannot delete client with active sessions
    - Invalid recurrence pattern
    """

    def __init__(
        self,
        message: str = "Validation failed",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, status_code=422, detail=detail)


class ConflictError(AppException):
    """
    Raised when operation conflicts with existing state.

    Examples:
    - Email already registered
    - Phone number already in use
    - Duplicate record
    """

    def __init__(
        self,
        message: str = "Resource already exists",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, status_code=409, detail=detail)


class ExternalServiceError(AppException):
    """
    Raised when external service call fails.

    Examples:
    - Anthropic API error
    - WhatsApp API error
    - Third-party service unavailable
    """

    def __init__(
        self,
        message: str = "External service error",
        service_name: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        detail = detail or {}
        if service_name:
            detail["service"] = service_name
        super().__init__(message=message, status_code=502, detail=detail)


class RateLimitError(AppException):
    """
    Raised when rate limit is exceeded.

    Examples:
    - Too many API requests
    - Too many WhatsApp messages sent
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        detail = detail or {}
        if retry_after:
            detail["retry_after"] = retry_after
        super().__init__(message=message, status_code=429, detail=detail)


class DatabaseError(AppException):
    """
    Raised when database operation fails.

    Examples:
    - Connection timeout
    - Constraint violation (caught at application layer)
    - Transaction rollback
    """

    def __init__(
        self,
        message: str = "Database error",
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, status_code=500, detail=detail)
