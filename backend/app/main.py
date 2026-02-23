# backend/app/main.py
import os
import logging
from contextlib import asynccontextmanager

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base, SessionLocal
from app.models import player  # ensures all tables are created

from app.routers import players, games, projections, odds, auth
from app.services.schema_compat import ensure_projection_history_schema


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Environment helpers ───────────────────────────────────────────────────────
def _get_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")

ENV = os.getenv("ENV", "development").lower()
IS_PROD = ENV in ("production", "prod")

# Comma-separated list of allowed origins
# Example prod: ALLOWED_ORIGINS=https://app.yourdomain.com
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]

# In prod, prefer Alembic migrations only (no create_all).
# You can still force create_all with FORCE_CREATE_ALL=true if needed.
FORCE_CREATE_ALL = _get_bool("FORCE_CREATE_ALL", default=False)

# Only run schema compatibility patch in dev by default.
# If you still want it in prod, set RUN_SCHEMA_COMPAT=true
RUN_SCHEMA_COMPAT = _get_bool("RUN_SCHEMA_COMPAT", default=not IS_PROD)

# ── Scheduler ────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone=pytz.utc)

NIGHTLY_JOB_TIMEZONE = pytz.timezone("America/New_York")

def run_nightly_update():
    """Runs the incremental NBA stats update in its own DB session."""
    logger.info("Nightly NBA stats update starting...")
    try:
        from app.services.nba_fetcher import nightly_update
        nightly_update()
    except Exception as e:
        logger.exception(f"Nightly NBA stats update failed: {e}")


def run_nightly_odds_update():
    """Fetches latest NBA odds after the stats refresh completes."""
    logger.info("Nightly NBA odds update starting...")
    try:
        from app.services.odds_fetcher import fetch_todays_odds

        result = fetch_todays_odds()
        logger.info(
            "Nightly NBA odds update complete — games=%s player_lines=%s game_lines=%s errors=%s",
            result.get("games_processed", 0),
            result.get("lines_saved", 0),
            result.get("game_lines_saved", 0),
            len(result.get("errors", [])),
        )
    except Exception as e:
        logger.exception(f"Nightly NBA odds update failed: {e}")


def run_nightly_pipeline():
    """Runs the full nightly pipeline: stats refresh first, then odds."""
    logger.info("Nightly pipeline starting (stats + odds)...")
    run_nightly_update()
    run_nightly_odds_update()
    logger.info("Nightly pipeline finished")

# 05:00 ET daily — full nightly refresh (stats + projections + odds)
scheduler.add_job(
    run_nightly_pipeline,
    CronTrigger(hour=5, minute=0, timezone=NIGHTLY_JOB_TIMEZONE),
    id="nba_nightly_pipeline",
    name="NBA nightly pipeline — 5am ET",
    replace_existing=True,
)

# ── App lifespan ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if FORCE_CREATE_ALL or not IS_PROD:
        # Dev-friendly. In prod, rely on Alembic migrations instead.
        Base.metadata.create_all(bind=engine)
        logger.info("DB create_all executed (dev mode or FORCE_CREATE_ALL=true)")
    else:
        logger.info("DB create_all skipped (production) — expecting Alembic migrations")

    if RUN_SCHEMA_COMPAT:
        db = SessionLocal()
        try:
            ensure_projection_history_schema(db)
            logger.info("Schema compatibility ensured (RUN_SCHEMA_COMPAT enabled)")
        except Exception as e:
            logger.exception(f"Schema compat step failed: {e}")
        finally:
            db.close()
    else:
        logger.info("Schema compatibility step skipped (RUN_SCHEMA_COMPAT=false)")

    scheduler.start()
    logger.info("APScheduler started — nightly pipeline scheduled for 5am ET")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")


# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Sports Analytics API",
    version="2.2.0",
    description="NBA Props Analytics Engine — Phase 2 with Auto Stats Update",
    lifespan=lifespan,
)

# ✅ Add CORS ONCE (env-driven)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(players.router)
app.include_router(games.router)
app.include_router(projections.router)
app.include_router(odds.router)
app.include_router(auth.router)

@app.get("/health")
def health_check():
    return {
        "status": "online",
        "version": "2.2.0",
        "env": ENV,
        "allowed_origins": ALLOWED_ORIGINS,
        "scheduler": {
            "running": scheduler.running,
            "jobs": [j.name for j in scheduler.get_jobs()],
        },
    }
