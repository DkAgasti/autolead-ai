import datetime
import logging
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.models import Lead, EmailThread, SystemLog
from app.services.scraper import run_harvester
from app.services.smtp_engine import send_native_email_async, is_within_client_window, anti_ban_delay, get_smtp_credentials
from app.services.imap_engine import poll_imap_inbox

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def scheduled_harvester_job():
    """Daily harvester scheduled at 10:00 AM IST."""
    logger.info("Executing scheduled Daily Harvester job (10:00 AM IST)...")
    await run_harvester()

async def scheduled_imap_poller_job():
    """Background worker polling Gmail INBOX over IMAP every 2 minutes."""
    try:
        await poll_imap_inbox()
    except Exception as e:
        logger.error(f"Scheduled IMAP poller failed: {e}")

async def scheduled_outbound_queue_dispatcher():
    """
    Checks leads in SCHEDULED status.
    Verifies if current time in recipient's timezone is between 9:30 AM and 11:00 AM.
    Dispatches outbound pitches via direct SMTP with anti-ban throttling.
    """
    db = SessionLocal()
    try:
        scheduled_leads = db.query(Lead).filter(Lead.status == "SCHEDULED").all()
        if not scheduled_leads:
            return

        creds = get_smtp_credentials()

        for lead in scheduled_leads:
            # Check client timezone window (9:30 AM - 11:00 AM recipient local time)
            in_window = is_within_client_window(lead.timezone or "America/New_York")
            if not in_window:
                continue

            if not lead.email:
                continue

            logger.info(f"Dispatching scheduled pitch to {lead.email} ({lead.timezone})...")
            
            success, msg_info, message_id = await send_native_email_async(
                recipient_email=lead.email,
                subject=lead.subject_line or f"Question regarding {lead.title[:30]}",
                body_text=lead.email_body or ""
            )

            if success:
                lead.status = "SENT"
                lead.sent_at = datetime.datetime.utcnow()
                lead.message_id = message_id

                # Record outbound thread
                thread = EmailThread(
                    lead_id=lead.id,
                    direction="OUTBOUND",
                    sender=creds["user"] or "outreach@gmail.com",
                    recipient=lead.email,
                    subject=lead.subject_line or "Outreach Pitch",
                    body_text=lead.email_body or "",
                    message_id=message_id,
                    status="SENT",
                    created_at=datetime.datetime.utcnow()
                )
                db.add(thread)
                db.commit()

                # Anti-ban throttle delay between consecutive emails
                await anti_ban_delay()

    except Exception as e:
        logger.error(f"Error in outbound dispatcher: {e}")
        db.rollback()
    finally:
        db.close()

def start_scheduler():
    """Initializes and starts the APScheduler jobs."""
    if scheduler.running:
        return

    # 1. Daily Harvester at 10:00 AM IST (Asia/Kolkata)
    ist_tz = pytz.timezone("Asia/Kolkata")
    scheduler.add_job(
        scheduled_harvester_job,
        trigger=CronTrigger(hour=10, minute=0, timezone=ist_tz),
        id="daily_harvester",
        replace_existing=True
    )

    # 2. Outbound Dispatcher (checks queue every 3 minutes)
    scheduler.add_job(
        scheduled_outbound_queue_dispatcher,
        trigger=IntervalTrigger(minutes=3),
        id="queue_dispatcher",
        replace_existing=True
    )

    # 3. IMAP Inbound Reply Listener (polls every 2 minutes)
    scheduler.add_job(
        scheduled_imap_poller_job,
        trigger=IntervalTrigger(minutes=2),
        id="imap_poller",
        replace_existing=True
    )

    scheduler.start()
    logger.info("APScheduler initialized: Daily Harvester (10:00 AM IST), Timezone Dispatcher (3m), IMAP Poller (2m).")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()

