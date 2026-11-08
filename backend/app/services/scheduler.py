import datetime
import logging
import json
import asyncio
import random
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
_dispatcher_lock = asyncio.Lock()

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
                    if not lead.email:
                        lead.status = "NEEDS_EMAIL"
                        logger.info(f"Lead #{lead.id} ({lead.title[:35]}) hiring but lacks email -> marked NEEDS_EMAIL")
                    elif autonomous:
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

        # Step 4: Dispatch daily WhatsApp, Telegram & email summary
        try:
            from app.services.whatsapp_notifier import generate_and_send_daily_report
            await generate_and_send_daily_report()
            logger.info("Dispatched post-outreach WhatsApp daily summary.")
        except Exception as we:
            logger.warning(f"Could not dispatch post-outreach WhatsApp summary: {we}")

        try:
            from app.services.telegram_notifier import generate_and_send_telegram_report
            await generate_and_send_telegram_report()
            logger.info("Dispatched post-outreach Telegram daily summary.")
        except Exception as te:
            logger.warning(f"Could not dispatch post-outreach Telegram summary: {te}")

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

async def scheduled_whatsapp_report_job():
    """Daily summary dispatcher sending activity metrics to Telegram, WhatsApp & email."""
    try:
        from app.services.telegram_notifier import generate_and_send_telegram_report
        tres = await generate_and_send_telegram_report()
        logger.info(f"Scheduled Telegram report status: {tres.get('telegram_status')}")
    except Exception as te:
        logger.warning(f"Scheduled Telegram report notice: {te}")

    try:
        from app.services.whatsapp_notifier import generate_and_send_daily_report
        res = await generate_and_send_daily_report()
        logger.info(f"Scheduled WhatsApp summary dispatched: {res.get('whatsapp_status')}")
    except Exception as e:
        logger.error(f"Scheduled WhatsApp report failed: {e}")

async def scheduled_outbound_queue_dispatcher():
    """
    Automated Outbound Dispatcher:
    Picks up all leads in SCHEDULED or ANALYZED status.
    Dispatches personalized cold email via direct Gmail SMTP (smtp.gmail.com:465 SSL).
    Applies anti-ban throttle (45-90s random delay for real emails) between consecutive sends.
    """
    if _dispatcher_lock.locked():
        logger.info("Outbound queue dispatcher already running, skipping overlapping execution.")
        return

    async with _dispatcher_lock:
        db = SessionLocal()
        try:
            autonomous = is_autonomous_outreach_enabled()
            if autonomous:
                scheduled_leads = db.query(Lead).filter(
                    Lead.status.in_(["SCHEDULED", "ANALYZED"]),
                    Lead.is_hiring == True,
                    Lead.email.isnot(None)
                ).order_by(Lead.id.asc()).all()
            else:
                scheduled_leads = db.query(Lead).filter(
                    Lead.status == "SCHEDULED",
                    Lead.email.isnot(None)
                ).order_by(Lead.id.asc()).all()

            if not scheduled_leads:
                return

            creds = get_smtp_credentials()
            respect_tz = is_respect_timezone_window_enabled()
            logger.info(f"Outbound Dispatcher: Processing {len(scheduled_leads)} leads for automated dispatch...")

            for lead in scheduled_leads:
                # Check client timezone window if enabled
                if respect_tz:
                    in_window = is_within_client_window(lead.timezone or "America/New_York")
                    if not in_window:
                        logger.info(f"Lead #{lead.id} waiting for local timezone window ({lead.timezone})...")
                        continue

                if not lead.email or lead.email.endswith(".placeholder") or "@reddit-contact." in lead.email:
                    logger.info(f"Lead #{lead.id} has no real email address; moving to NEEDS_EMAIL")
                    lead.status = "NEEDS_EMAIL"
                    lead.updated_at = datetime.datetime.utcnow()
                    db.commit()
                    continue

                subj = lead.subject_line or f"Collaboration regarding {lead.title[:30]}"
                body = lead.email_body
                if not body:
                    body = (
                        f"Hi {lead.lead_name or 'there'},\n\n"
                        f"I came across your posting regarding {lead.title}.\n"
                        f"{lead.audit_summary or 'We specialize in modern web & AI software engineering.'}\n\n"
                        f"Would you be open to connecting for a quick 10-minute introductory call?\n\n"
                        f"Best regards,\n{creds.get('sender_name') or 'CodePro'}"
                    )

                logger.info(f"Auto-Dispatching email to {lead.email} via Gmail SMTP...")

                success, msg_info, message_id = await send_native_email_async(
                    recipient_email=lead.email,
                    subject=subj,
                    body_text=body
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
                        subject=subj,
                        body_text=body,
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

                    # Anti-ban delay between consecutive real emails
                    await anti_ban_delay()
                else:
                    logger.warning(f"Outbound dispatch not possible for {lead.email}: {msg_info}")
                    if "Undeliverable recipient domain" in msg_info or "Null MX" in msg_info or "NXDOMAIN" in msg_info:
                        lead.status = "BOUNCED"
                    else:
                        lead.status = "FAILED"
                    lead.updated_at = datetime.datetime.utcnow()
                    log = SystemLog(
                        level="WARNING",
                        module="SMTP",
                        message=f"Blocked dispatch to {lead.email}: {msg_info}"
                    )
                    db.add(log)
                    db.commit()

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
    time_str = getattr(settings, "DAILY_SCRAPE_TIME_IST", "10:00")
    try:
        hour, minute = map(int, time_str.split(":"))
    except Exception:
        hour, minute = 10, 0

    scheduler.add_job(
        scheduled_harvester_job,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=ist_tz),
        id="daily_harvester",
        replace_existing=True
    )

    # 2. Outbound Dispatcher (checks queue every 2 minutes)
    scheduler.add_job(
        scheduled_outbound_queue_dispatcher,
        trigger=IntervalTrigger(minutes=2),
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

    # 4. Daily Evening WhatsApp Wrap-Up Report at 20:00 IST (8:00 PM)
    report_time_str = getattr(settings, "DAILY_REPORT_TIME_IST", "20:00")
    try:
        r_hour, r_minute = map(int, report_time_str.split(":"))
    except Exception:
        r_hour, r_minute = 20, 0

    scheduler.add_job(
        scheduled_whatsapp_report_job,
        trigger=CronTrigger(hour=r_hour, minute=r_minute, timezone=ist_tz),
        id="daily_evening_whatsapp_report",
        replace_existing=True
    )

    scheduler.start()
    logger.info(f"APScheduler initialized: Autonomous {hour:02d}:{minute:02d} IST Pipeline, Daily {r_hour:02d}:{r_minute:02d} IST WhatsApp Report, Queue (2m), IMAP (2m).")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
