"""
FastAPI application entry point.
Configures middleware, lifespan events, and health check endpoint.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import text

from app.config import settings
from app.database import engine


# --- Rate limiter ---
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


# --- Lifespan (startup / shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify database connection on startup, cleanup on shutdown."""
    # Startup: test database connection
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    print("✅ Database connection verified")
    yield
    # Shutdown: dispose engine
    await engine.dispose()
    print("🛑 Database engine disposed")


# --- FastAPI app ---
app = FastAPI(
    title="MediApp API",
    description="Sistema de Gestión de Citas Médicas — API REST",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# --- Middleware ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


# --- Register routers ---
from app.routers import auth, patients, appointments, notifications, medical_records, reports, doctors

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(patients.router, prefix=settings.api_prefix)
app.include_router(doctors.router, prefix=settings.api_prefix)
app.include_router(appointments.router, prefix=settings.api_prefix)
app.include_router(notifications.router, prefix=settings.api_prefix)
app.include_router(medical_records.router, prefix=settings.api_prefix)
app.include_router(reports.router, prefix=settings.api_prefix)


# --- Health check ---
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint to verify the API is running."""
    return {"status": "ok", "environment": settings.environment}
