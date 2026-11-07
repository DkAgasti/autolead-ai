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

@router.post("/send-test-email")
async def send_test_email(db: Session = Depends(get_db)):
    """Dispatches a test cold pitch to the configured EMAIL_USER to verify SMTP delivery."""
    from app.services.smtp_engine import send_native_email_async, get_smtp_credentials
    creds = get_smtp_credentials()
    if not creds.get("user"):
        return {"status": "error", "message": "EMAIL_USER is not configured in .env"}

    recipient = creds["user"]
    subject = f"AutoLead AI Test: Outreach Verification for {creds.get('sender_name', 'CodePro')}"
    body = (
        f"Hi there,\n\n"
        f"This is a verified test email sent directly via Google SMTP (smtp.gmail.com:465 SSL) "
        f"using your configured App Password.\n\n"
        f"Your AutoLead AI cold outreach engine is connected and ready to send pitches.\n\n"
        f"Sender: {creds.get('sender_name')}\n"
        f"Recipient: {recipient}\n"
        f"Protocol: Direct Native smtplib (No 3rd party APIs)\n\n"
        f"Best regards,\nAutoLead AI Agent"
    )

    success, msg_info, message_id = await send_native_email_async(
        recipient_email=recipient,
        subject=subject,
        body_text=body
    )

    if success:
        log = SystemLog(
            level="SUCCESS",
            module="SMTP",
            message=f"Test email successfully delivered to {recipient}",
            details=f"Message-ID: {message_id}"
        )
        db.add(log)
        db.commit()
        return {"status": "success", "message": f"Test email delivered to {recipient}!", "message_id": message_id}
    else:
        return {"status": "error", "message": msg_info}

@router.post("/run-autopilot")
async def run_autopilot_pipeline(db: Session = Depends(get_db)):
    """
    1-Click Auto-Pilot:
    1. Scrapes fresh live leads from WeWorkRemotely, HackerNews, and Reddit
    2. Runs Gemini AI analysis & cold pitch generation on all raw leads
    """
    from app.api.leads import bulk_analyze_raw_leads

    # 1. Scrape
    scrape_res = await run_harvester(db)

    # 2. Analyze
    analyze_res = await bulk_analyze_raw_leads(db)

    return {
        "status": "success",
        "scraped": scrape_res.get("added", 0),
        "analyzed": analyze_res.get("analyzed_count", 0)
    }


