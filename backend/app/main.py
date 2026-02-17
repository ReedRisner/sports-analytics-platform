# backend/app/main.py
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from app.database import engine, Base
from app.models import player  # ensures all tables are created

from app.routers import players, games, projections, odds

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone=pytz.utc)

def run_odds_fetch():
    """Called by the scheduler. Runs the odds fetch in its own DB session."""
    logger.info("Scheduled odds fetch starting...")
    try:
        from app.services.odds_fetcher import fetch_todays_odds
        result = fetch_todays_odds()
        logger.info(f"Scheduled odds fetch complete: {result}")
    except Exception as e:
        logger.exception(f"Scheduled odds fetch failed: {e}")

# Midnight PST = 08:00 UTC
# Noon PST     = 20:00 UTC
scheduler.add_job(
    run_odds_fetch,
    CronTrigger(hour=8, minute=0, timezone="UTC"),
    id="odds_fetch_morning",
    name="Odds fetch — midnight PST",
    replace_existing=True,
)
scheduler.add_job(
    run_odds_fetch,
    CronTrigger(hour=20, minute=0, timezone="UTC"),
    id="odds_fetch_evening",
    name="Odds fetch — noon PST",
    replace_existing=True,
)


# ── App lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    scheduler.start()
    logger.info("APScheduler started — odds fetching at 08:00 and 20:00 UTC")
    yield
    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Sports Analytics API",
    version="2.1.0",
    description="NBA Props Analytics Engine — Phase 2 with Live Odds",
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


@app.get("/health")
def health_check():
    return {
        "status":  "online",
        "version": "2.1.0",
        "scheduler": {
            "running": scheduler.running,
            "jobs":    [j.name for j in scheduler.get_jobs()],
        }
    }