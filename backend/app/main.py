"""
Fraud Rule Engine – FastAPI Application
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import get_settings

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s – %(message)s",
)
logger   = logging.getLogger(__name__)
settings = get_settings()

# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Fraud Rule Engine",
    version=settings.APP_VERSION,
    description=(
        "LLM-powered fraud detection rule engine. "
        "Generate rules from a scenario prompt, evaluate them against "
        "your synthetic dataset and get precision/recall metrics."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow all origins in dev; tighten in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


# ─── Global exception handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception("Unhandled error on %s: %s", request.url, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs."},
    )
