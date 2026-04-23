"""
FastAPI main application entry point.

This module sets up:
- FastAPI app with CORS
- Database lifecycle management (startup/shutdown)
- Custom exception handlers
- Router inclusion for all modules
- Health check endpoint
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.database import check_database_connection, close_db
from core.exceptions import AppException

# Import routers (will be implemented later)
# from auth.router import router as auth_router
# from professionals.router import router as professionals_router
# from clients.router import router as clients_router
# from agenda.router import router as agenda_router
# from reports.router import router as reports_router
# from whatsapp.router import router as whatsapp_router


# ============================================================================
# Lifespan Management
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application lifecycle (startup and shutdown).

    Startup:
    - Verify database connection
    - Log startup message

    Shutdown:
    - Close database connections gracefully
    - Clean up resources

    This replaces the deprecated @app.on_event("startup") decorator.
    """
    # Startup
    print(f"🚀 Starting Secretária Digital API in {settings.ENVIRONMENT} mode...")

    # Check database connection
    if await check_database_connection():
        print("✅ Database connection established")
    else:
        print("❌ Database connection failed")
        raise RuntimeError("Failed to connect to database")

    yield

    # Shutdown
    print("🛑 Shutting down Secretária Digital API...")
    await close_db()
    print("✅ Database connections closed")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Secretária Digital API",
    description="API backend para secretária inteligente com IA para profissionais autônomos",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,  # Disable docs in production
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)


# ============================================================================
# CORS Middleware
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Exception Handlers
# ============================================================================


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Handle custom application exceptions.

    Converts AppException instances to JSON responses with appropriate
    status codes and error details.

    Response format:
    {
        "error": {
            "message": "Human-readable error message",
            "detail": {"key": "additional context"}
        }
    }
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"message": exc.message, "detail": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors.

    This catches validation errors from request body, query params, and path params.
    Returns a 422 response with detailed validation errors.

    Response format:
    {
        "error": {
            "message": "Validation failed",
            "detail": {
                "errors": [{"loc": ["body", "email"], "msg": "invalid email", "type": "value_error.email"}]
            }
        }
    }
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "message": "Validation failed",
                "detail": {"errors": exc.errors()},
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unexpected exceptions.

    This ensures no exception leaks implementation details to the client.
    In production, logs the full error but returns a generic message.

    Response format:
    {
        "error": {
            "message": "Internal server error",
            "detail": {}
        }
    }
    """
    # In production, log the exception here (use proper logging)
    if settings.DEBUG:
        print(f"❌ Unhandled exception: {exc}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "Internal server error",
                "detail": {"type": type(exc).__name__} if settings.DEBUG else {},
            }
        },
    )


# ============================================================================
# Health Check Endpoint
# ============================================================================


@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns:
    - 200 OK if service is healthy and database is reachable
    - 503 Service Unavailable if database connection fails

    This endpoint is used by:
    - Load balancers
    - Monitoring systems
    - Railway health checks
    """
    db_healthy = await check_database_connection()

    if not db_healthy:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "unreachable"},
        )

    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "database": "connected",
    }


# ============================================================================
# Router Inclusion
# ============================================================================

# TODO: Uncomment as routers are implemented
# app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
# app.include_router(professionals_router, prefix="/api/v1/professionals", tags=["Professionals"])
# app.include_router(clients_router, prefix="/api/v1/clients", tags=["Clients"])
# app.include_router(agenda_router, prefix="/api/v1/agenda", tags=["Agenda"])
# app.include_router(reports_router, prefix="/api/v1/reports", tags=["Reports"])
# app.include_router(whatsapp_router, prefix="/api/v1/whatsapp", tags=["WhatsApp"])


# ============================================================================
# Development Server (optional - use uvicorn CLI instead)
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
