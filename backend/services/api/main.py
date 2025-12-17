"""
Main API Application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.routes import router

app = FastAPI(
    title="PSP Reconciliation Platform API",
    description="Production-grade PSP Reconciliation Platform for iGaming operators",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

