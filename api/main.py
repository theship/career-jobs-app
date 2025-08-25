"""
Career Jobs App - FastAPI Backend
Phase 1: Foundation & Authentication
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    print("Starting Career Jobs App API...")
    yield
    # Shutdown
    print("Shutting down Career Jobs App API...")


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
    return {"status": "healthy", "service": "career-jobs-api", "version": "0.1.0"}


# Import and include routers
from api.routes import auth, resumes

app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(resumes.router, prefix="/api/v1", tags=["resumes"])
# app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
# app.include_router(scoring.router, prefix="/api/v1/scores", tags=["scoring"])
# app.include_router(export.router, prefix="/api/v1/export", tags=["export"])
