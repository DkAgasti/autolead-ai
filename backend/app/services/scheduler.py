import datetime
import logging
import json
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import SessionLocal
from app.models import Lead, EmailThread, AppSetting, SystemLog
from app.services.scraper import run_harvester
from app.services.website_auditor import audit_website
from app.services.gemini_engine import analyze_lead_with_gemini
from app.services.smtp_engine import send_native_email_async, is_within_client_window, anti_ban_delay, get_smtp_credentials
from app.services.imap_engine import poll_imap_inbox

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

def is_autonomous_outreach_enabled() -> bool:
    """Checks if fully autonomous outreach pipeline is active."""
    try:
        db = SessionLocal()
        s = db.query(AppSetting).filter(AppSetting.key == "autonomous_outreach").first()
        db.close()
        if s and s.value:
            return s.value.strip().lower() in ["true", "1", "yes"]
    except Exception:
        pass
    return getattr(settings, "AUTONOMOUS_OUTREACH", True)

def is_respect_timezone_window_enabled() -> bool:
    """Checks if queue dispatcher should restrict sending to 9:30 AM - 11:00 AM recipient local time."""
    try:
        db = SessionLocal()
        s = db.query(AppSetting).filter(AppSetting.key == "respect_timezone_window").first()
        db.close()
        if s and s.value:
            return s.value.strip().lower() in ["true", "1", "yes"]
    except Exception:
        pass
    return getattr(settings, "RESPECT_TIMEZONE_WINDOW", False)

async def scheduled_harvester_job():
    """
    100% Fully Autonomous Pipeline triggered at 10:00 AM IST:
    1. Scrapes fresh live leads from WeWorkRemotely, HackerNews, and Reddit
    2. Automatically analyzes every raw lead with Gemini 2.5/3.8 Flash
    3. If AUTONOMOUS_OUTREACH=true:
       Automatically queues verified hiring leads into SCHEDULED status,
       and starts outbound dispatch via direct Gmail SMTP with anti-ban delay!
    """
    logger.info("Executing Autonomous 10:00 AM IST Pipeline...")

    # Step 1: Auto-Harvest leads
    harvest_result = await run_harvester()
    logger.info(f"Auto-Harvest result: {harvest_result}")

    # Step 2: Auto-Analyze raw leads with Gemini
    db = SessionLocal()
    analyzed_count = 0
    auto_scheduled_count = 0

    try:
        raw_leads = db.query(Lead).filter(Lead.status == "RAW").all()
        logger.info(f"Auto-Analyzing {len(raw_leads)} raw leads with Gemini...")

        autonomous = is_autonomous_outreach_enabled()

        for lead in raw_leads:
            try:
                audit_res = None
                if lead.website_url:
                    audit_res = await audit_website(lead.website_url)

                res = await analyze_lead_with_gemini(
                    lead.title,
                    lead.raw_text,
                    lead.website_url,
                    audit_res
                )

                lead.is_hiring = res["is_hiring"]
                lead.lead_name = res["lead_name"]
                lead.pain_points = json.dumps(res["pain_points"])
                lead.audit_summary = res["audit_summary"]
                lead.subject_line = res["subject_line"]
                lead.email_body = res["email_body"]

                if res["is_hiring"]:
                    if autonomous:
                        # Auto-schedule for automated outbound dispatch
                        lead.status = "SCHEDULED"
                        lead.scheduled_at = datetime.datetime.utcnow()
                        auto_scheduled_count += 1
                        logger.info(f"Lead #{lead.id} ({lead.title[:35]}) verified -> AUTO-SCHEDULED for SMTP!")
                    else:
                        lead.status = "ANALYZED"
                else:
                    lead.status = "FILTERED_OUT"

                lead.updated_at = datetime.datetime.utcnow()
                analyzed_count += 1

            except Exception as le:
                logger.error(f"Error analyzing lead #{lead.id}: {le}")

        db.commit()

        log = SystemLog(
            level="SUCCESS",
            module="SCHEDULER",
            message=f"Autonomous 10:00 AM cycle: Analyzed {analyzed_count} leads, Auto-Scheduled {auto_scheduled_count} for SMTP dispatch."
        )
        db.add(log)
        db.commit()

        # Step 3: Automatically trigger outbound dispatch if autonomous
        if autonomous and auto_scheduled_count > 0:
            logger.info("Starting automated outbound SMTP dispatch with anti-ban delay...")
            await scheduled_outbound_queue_dispatcher()

    except Exception as e:
        logger.error(f"Error in autonomous pipeline: {e}")
        db.rollback()
    finally:
        db.close()

async def scheduled_imap_poller_job():
    """Background worker polling Gmail INBOX over IMAP every 2 minutes."""
    try:
        await poll_imap_inbox()
    except Exception as e:
        logger.error(f"Scheduled IMAP poller failed: {e}")

async def scheduled_outbound_queue_dispatcher():
    """
    Automated Outbound Dispatcher:
    Picks up all leads in SCHEDULED status.
    Dispatches personalized cold email via direct Gmail SMTP (smtp.gmail.com:465 SSL).
    Applies anti-ban throttle (45-90s random delay) between consecutive sends.
    """
    db = SessionLocal()
    try:
        scheduled_leads = db.query(Lead).filter(Lead.status == "SCHEDULED").all()
        if not scheduled_leads:
            return

        creds = get_smtp_credentials()
        respect_tz = is_respect_timezone_window_enabled()

        for lead in scheduled_leads:
            # Check client timezone window if enabled
            if respect_tz:
                in_window = is_within_client_window(lead.timezone or "America/New_York")
                if not in_window:
                    logger.info(f"Lead #{lead.id} waiting for local timezone window ({lead.timezone})...")
                    continue

            if not lead.email:
                continue

            logger.info(f"Auto-Dispatching email to {lead.email} via Gmail SMTP...")

            success, msg_info, message_id = await send_native_email_async(
                recipient_email=lead.email,
                subject=lead.subject_line or f"Question regarding {lead.title[:30]}",
                body_text=lead.email_body or ""
            )

            if success:
                lead.status = "SENT"
                lead.sent_at = datetime.datetime.utcnow()
                lead.message_id = message_id

                thread = EmailThread(
                    lead_id=lead.id,
                    direction="OUTBOUND",
                    sender=creds["user"] or "5yearcodepro.dev@gmail.com",
                    recipient=lead.email,
                    subject=lead.subject_line or "Outreach Pitch",
                    body_text=lead.email_body or "",
                    message_id=message_id,
                    status="SENT",
                    created_at=datetime.datetime.utcnow()
                )
                db.add(thread)

                log = SystemLog(
                    level="SUCCESS",
                    module="SMTP",
                    message=f"Autonomous Outbound: Dispatched pitch to {lead.email}",
                    details=f"Message-ID: {message_id}"
                )
                db.add(log)
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

    # 1. Daily Autonomous Pipeline at 10:00 AM IST (Asia/Kolkata)
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
    logger.info("APScheduler initialized: Autonomous 10:00 AM IST Pipeline, Queue Dispatcher (3m), IMAP Poller (2m).")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
