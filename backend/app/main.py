"""
FastAPI application setup and main entry point.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api import circulars, obligations, compliance, graph
from app.api import evidence as evidence_api
from app.api import audit_api
from app.api import extended as extended_api
from app.api import notifications as notifications_api

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RegGraph API",
    description="Regulatory Obligation Graph System for SEBI Compliance",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(circulars.router, prefix="/api/v1/circulars", tags=["Circulars"])
app.include_router(obligations.router, prefix="/api/v1/obligations", tags=["Obligations"])
app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["Compliance"])
app.include_router(graph.router, prefix="/api/v1/graph", tags=["Graph"])
app.include_router(evidence_api.router, prefix="/api/v1/evidence", tags=["Evidence"])
app.include_router(audit_api.router, prefix="/api/v1/audit", tags=["Audit"])
app.include_router(extended_api.router, prefix="/api/v1", tags=["Extended"])
app.include_router(notifications_api.router, prefix="/api/v1/notifications", tags=["Notifications"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "regraph"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "RegGraph API",
        "version": "0.1.0",
        "description": "Regulatory Obligation Graph for SEBI Compliance",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT
    )
