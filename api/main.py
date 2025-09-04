"""
Career Jobs App - FastAPI Backend
Phase 1: Foundation & Authentication
"""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.utils.security import limiter

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting Career Jobs App API...")
    
    # Verify Redis connection (REQUIRED)
    from api.utils.redis_client import verify_redis_connection
    logger.info("Verifying Redis connection...")
    verify_redis_connection()  # Will exit if Redis not available
    logger.info("Redis connection verified ✓")
    
    # Initialize HMAC security
    from api.utils.config import get_settings
    from api.utils.hmac_security import initialize_hmac
    settings = get_settings()
    if settings.hmac_secret:
        initialize_hmac(settings.hmac_secret)
        logger.info("HMAC security initialized ✓")
    else:
        logger.warning("HMAC_SECRET not configured - request signing disabled")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Career Jobs App API...")
    
    # Close Redis connection
    from api.utils.redis_client import close_redis_connection
    close_redis_connection()


# Create FastAPI app
app = FastAPI(
    title="Career Jobs App API",
    description="AI-powered job matching and career development platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS - Locked down to only Next.js
# In production, FastAPI should only accept requests from Next.js proxy
if os.getenv("ENVIRONMENT") == "production":
    # Production: Deny all CORS (only server-to-server allowed)
    allowed_origins = []
else:
    # Development: Only allow Next.js origins
    allowed_origins = [
        "http://localhost:3000",  # Next.js dev server
        os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000"),
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Empty list = no CORS in production
    allow_credentials=False,  # No cookies needed (using service auth)
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "X-Service-Secret",
        "X-User-Id",
        "X-User-Email",
        "X-User-Token",
    ],
    expose_headers=["X-Request-Id"],  # For request tracking
    max_age=3600,  # Cache preflight for 1 hour
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Career Jobs App API",
        "version": "0.1.0",
        "status": "operational",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": "career-jobs-api",
        "version": "0.1.0",
    }


# Import and include routers (moved here to avoid E402)
from api.routes import auth, jobs, pitch, research, resumes, scoring  # noqa: E402

app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(resumes.router, prefix="/api/v1", tags=["resumes"])
app.include_router(jobs.router, tags=["jobs"])  # Prefix already in router
app.include_router(
    scoring.router, prefix="/api/v1", tags=["scoring"]
)  # Add prefix here
app.include_router(research.router, tags=["research"])  # Prefix already in router
app.include_router(pitch.router, tags=["pitch"])  # Prefix already in router
# app.include_router(export.router, prefix="/api/v1/export", tags=["export"])
