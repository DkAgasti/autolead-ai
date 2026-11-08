import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models import Lead, SystemLog
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.scraper import get_rich_curated_seed_leads
from app.api.leads import router as leads_router
from app.api.analytics import router as analytics_router
from app.api.settings import router as settings_router
from app.api.system import router as system_router
from app.api.reports import router as reports_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("autolead")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created.")

    # Seed demo leads if DB is brand new
    try:
        db = SessionLocal()
        if db.query(Lead).count() == 0:
            logger.info("Seeding initial high-intent leads across Reddit, LinkedIn, and Web...")
            seeds = get_rich_curated_seed_leads()
            for s in seeds:
                db.add(Lead(**s))
            db.commit()
            logger.info(f"Seeded {len(seeds)} leads.")
        db.close()
    except Exception as e:
        logger.warning(f"Initial seed notice: {e}")

    # Start APScheduler (Daily Harvester, Timezone Dispatcher, IMAP Poller)
    try:
        start_scheduler()
    except Exception as e:
        logger.error(f"Scheduler startup error: {e}")

    yield

    # Shutdown
    try:
        stop_scheduler()
    except Exception as e:
        logger.error(f"Scheduler shutdown error: {e}")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="End-to-End AI-Powered Lead Generation, Cold Outreach & Follow-up Agent with Direct SMTP/IMAP Gmail Engine",
    lifespan=lifespan
)

# CORS setup for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(leads_router)
app.include_router(analytics_router)
app.include_router(settings_router)
app.include_router(system_router)
app.include_router(reports_router)

@app.get("/")
def root():
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs": "/docs",
        "protocol": "Direct Native SMTP & IMAP (Zero 3rd party email APIs)"
    }

