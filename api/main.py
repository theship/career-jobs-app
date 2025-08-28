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

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting Career Jobs App API...")
    yield
    # Shutdown
    logger.info("Shutting down Career Jobs App API...")


# Create FastAPI app
app = FastAPI(
    title="Career Jobs App API",
    description="AI-powered job matching and career development platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://localhost:3001",  # Alternative port
        os.getenv("NEXT_PUBLIC_APP_URL", "http://localhost:3000"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


# Import and include routers
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
