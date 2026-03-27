"""
Zenith IQ — Entry Point
--------------------------
Starts the FastAPI application with all routers mounted.

Run:
    python main.py
    # or
    uvicorn main:app --reload
"""

import logging
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from api.routes import alpha_router, stock_router, analysis_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown hooks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once on startup and once on shutdown."""
    logger.info("=" * 60)
    logger.info("Zenith IQ starting up")
    logger.info(f"  Environment : {settings.app_env}")
    logger.info(f"  Host        : {settings.app_host}:{settings.app_port}")
    logger.info(f"  Gemini key  : {'set' if settings.gemini_api_key else 'MISSING'}")
    logger.info(f"  Supabase    : {'set' if settings.supabase_url else 'MISSING'}")
    logger.info(f"  NewsAPI     : {'set' if settings.news_api_key else 'not set (scraper fallback)'}")
    logger.info("=" * 60)
    yield
    logger.info("Zenith IQ shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Zenith IQ — AI Financial Analysis",
    description=(
        "Multi-agent system that detects hidden risks and alpha signals "
        "by combining SEC filings, news, social sentiment, insider trading, "
        "and technical analysis.\n\n"
        "**Quick start:** `POST /api/v1/alpha/analyse` with `{\"ticker\": \"AAPL\"}`"
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(alpha_router,    prefix="/api/v1")
app.include_router(stock_router,    prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Root routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"], include_in_schema=False)
async def root():
    return {
        "system":    "Zenith IQ",
        "version":   "2.0.0",
        "status":    "running",
        "docs":      "/docs",
        "endpoints": {
            "full_analysis":    "POST /api/v1/alpha/analyse",
            "quant_only":       "POST /api/v1/alpha/quant",
            "insider_only":     "POST /api/v1/alpha/insider",
            "news_only":        "POST /api/v1/alpha/news",
            "sentiment_only":   "POST /api/v1/alpha/sentiment",
            "contradict":       "POST /api/v1/analysis/contradict",
            "explain":          "POST /api/v1/analysis/explain",
            "stock_snapshot":   "GET  /api/v1/stocks/{ticker}",
        },
    }


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status":  "healthy",
        "env":     settings.app_env,
        "version": "2.0.0",
    }


# ---------------------------------------------------------------------------
# Global exception handler — never expose raw tracebacks to clients
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs for details."},
    )


# ---------------------------------------------------------------------------
# Dev runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
        log_level="info",
    )
