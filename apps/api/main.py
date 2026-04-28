"""
FastAPI main application entry point.

Setup:
- FastAPI app with strict CORS (explicit origins, credentials=True for cookies)
- Database lifecycle (startup/shutdown)
- Custom exception handlers (AppException -> JSON, ValidationError -> JSON)
- Router inclusion for all modules
- Health check endpoint
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agenda.router import router as agenda_router

# Routers
from auth.router import router as auth_router
from clients.router import router as clients_router
from core.config import settings
from core.database import check_database_connection, close_db
from core.exceptions import AppException
from professionals.router import router as professionals_router

# Future routers (uncomment as implemented)
# from reports.router import router as reports_router
# from whatsapp.router import router as whatsapp_router


# ============================================================================
# Lifespan Management
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: verify DB. Shutdown: close pool."""
    print(f"Starting Secretaria Digital API in {settings.ENVIRONMENT} mode...")

    if await check_database_connection():
        print("Database connection established")
    else:
        print("Database connection failed")
        raise RuntimeError("Failed to connect to database")

    yield

    print("Shutting down Secretaria Digital API...")
    await close_db()
    print("Database connections closed")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Secretaria Digital API",
    description="API backend para secretaria inteligente com IA para profissionais autonomos",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)


# ============================================================================
# CORS Middleware
# ============================================================================
#
# IMPORTANT: allow_credentials=True is mandatory for HttpOnly cookies
# (refresh_token) to be sent cross-origin. Therefore allow_origins must
# list explicit origins — "*" is forbidden when credentials=True.

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # e.g. ["http://localhost:5173"]
    allow_credentials=True,  # required for HttpOnly cookie
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# ============================================================================
# Exception Handlers
# ============================================================================


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Convert custom AppException subclasses to structured JSON response.

    Response format:
        {"error": {"message": "...", "detail": {...}}}
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"message": exc.message, "detail": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert Pydantic validation errors to 422 with field-level detail.

    Uses jsonable_encoder to handle Pydantic v2's model_validator errors,
    which include ctx={'error': ValueError(...)} — a non-JSON-serializable
    object that would cause a serialization failure if passed directly to
    JSONResponse.
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "message": "Validation failed",
                "detail": {"errors": jsonable_encoder(exc.errors())},
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: never leak implementation details to the client."""
    if settings.DEBUG:
        print(f"Unhandled exception: {exc}")

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
# Health Check
# ============================================================================


@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"], response_model=None)
async def health_check() -> dict | JSONResponse:
    """Health check used by load balancers and Railway."""
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

app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(professionals_router, prefix="/api/v1/professionals", tags=["Professionals"])

app.include_router(clients_router, prefix="/api/v1/clients", tags=["Clients"])

app.include_router(agenda_router, prefix="/api/v1/agenda", tags=["Agenda"])

# Uncomment as implemented:
# app.include_router(reports_router, prefix="/api/v1/reports", tags=["Reports"])
# app.include_router(whatsapp_router, prefix="/api/v1/whatsapp", tags=["WhatsApp"])


# ============================================================================
# Dev entrypoint
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
