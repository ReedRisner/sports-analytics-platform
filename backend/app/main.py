# backend/app/main.py
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi.middleware.cors import CORSMiddleware
import pytz

from app.database import engine, Base, SessionLocal
from app.models import player  # ensures all tables are created

from app.routers import players, games, projections, odds, auth
from app.services.schema_compat import ensure_projection_history_schema


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone=pytz.utc)

def run_nightly_update():
    """Runs the incremental NBA stats update in its own DB session."""
    logger.info("Nightly NBA stats update starting...")
    try:
        from app.services.nba_fetcher import nightly_update
        nightly_update()
    except Exception as e:
        logger.exception(f"Nightly NBA stats update failed: {e}")

# ── Times (all UTC) ───────────────────────────────────────────────────────────
# 03:00 PST = 11:00 UTC  — nightly stats update (after all West Coast games finish)
# Odds API access is intentionally manual-only.
# Run `python -m app.services.odds_fetcher` when you want fresh lines.

scheduler.add_job(
    run_nightly_update,
    CronTrigger(hour=11, minute=0, timezone="UTC"),
    id="nba_nightly_update",
    name="NBA stats nightly update — 3am PST",
    replace_existing=True,
)
# ── App lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)

    # Keep local/dev DBs compatible if migrations were not applied yet.
    db = SessionLocal()
    try:
        ensure_projection_history_schema(db)
    finally:
        db.close()

    scheduler.start()
    logger.info("APScheduler started — odds API fetches are manual-only")
    yield
    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Sports Analytics API",
    version="2.2.0",
    description="NBA Props Analytics Engine — Phase 2 with Auto Stats Update",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router)
app.include_router(games.router)
app.include_router(projections.router)
app.include_router(odds.router)
app.include_router(auth.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {
        "status":  "online",
        "version": "2.2.0",
        "scheduler": {
            "running": scheduler.running,
            "jobs":    [j.name for j in scheduler.get_jobs()],
        }
    }
