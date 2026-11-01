import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.database import get_db
from app.models import SystemLog, Lead
from app.services.scraper import run_harvester, get_rich_curated_seed_leads
from app.services.imap_engine import poll_imap_inbox
from app.services.scheduler import scheduled_outbound_queue_dispatcher

router = APIRouter(prefix="/api/system", tags=["system"])

@router.post("/harvest-now")
async def trigger_harvester(db: Session = Depends(get_db)):
    """Runs the harvester immediately (Reddit RSS, Dorks, Web)."""
    result = await run_harvester(db)
    return result

@router.post("/poll-imap-now")
async def trigger_imap_now():
    """Triggers IMAP polling immediately to check for replies."""
    result = await poll_imap_inbox()
    return result

@router.post("/dispatch-queue-now")
async def trigger_queue_dispatch():
    """Runs the outbound queue dispatcher immediately."""
    await scheduled_outbound_queue_dispatcher()
    return {"status": "success", "message": "Dispatched eligible queue items."}

@router.get("/logs")
def get_logs(limit: int = 50, db: Session = Depends(get_db)):
    """Retrieves recent system events and operational logs."""
    logs = db.query(SystemLog).order_by(SystemLog.id.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "level": l.level,
            "module": l.module,
            "message": l.message,
            "details": l.details,
            "created_at": l.created_at.isoformat()
        }
        for l in logs
    ]

@router.post("/seed-demo")
def seed_demo_leads(db: Session = Depends(get_db)):
    """Seeds rich sample leads across Reddit, LinkedIn, and Web for instant testing."""
    leads = get_rich_curated_seed_leads()
    added = 0
    for item in leads:
        existing = db.query(Lead).filter(Lead.title == item["title"]).first()
        if not existing:
            lead = Lead(
                source=item["source"],
                source_url=item.get("source_url"),
                title=item["title"],
                raw_text=item["raw_text"],
                author_id=item.get("author_id"),
                email=item.get("email"),
                website_url=item.get("website_url"),
                detected_country=item.get("detected_country", "United States"),
                timezone=item.get("timezone", "America/New_York"),
                status="RAW",
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow()
            )
            db.add(lead)
            added += 1
    db.commit()
    return {"status": "success", "added_count": added}
