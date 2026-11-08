import datetime
import logging
import urllib.parse
import pytz
import httpx
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Lead, EmailThread, SystemLog
from app.services.smtp_engine import send_native_email_async

logger = logging.getLogger(__name__)

def get_ist_day_bounds(target_date: Optional[datetime.date] = None) -> Tuple[datetime.datetime, datetime.datetime, str]:
    """Returns (start_utc, end_utc, formatted_ist_date) for a given date in Asia/Kolkata."""
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.datetime.now(ist)
    
    if target_date is None:
        target_date = now_ist.date()
        
    start_ist = ist.localize(datetime.datetime.combine(target_date, datetime.time.min))
    end_ist = ist.localize(datetime.datetime.combine(target_date, datetime.time.max))
    
    start_utc = start_ist.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    end_utc = end_ist.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    
    day_num = target_date.day
    suffix = "th" if 11 <= day_num <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day_num % 10, "th")
    formatted_date = f"{day_num}{suffix}{target_date.strftime('%b.%Y')}"
    
    return start_utc, end_utc, formatted_date

def generate_daily_metrics(target_date: Optional[datetime.date] = None, db: Optional[Session] = None) -> Dict[str, Any]:
    """Calculates daily lead generation, qualification, sent, and reply counts."""
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True
        
    try:
        start_utc, end_utc, formatted_date = get_ist_day_bounds(target_date)
        
        # Leads captured today
        total_leads = db.query(Lead).filter(Lead.created_at >= start_utc, Lead.created_at <= end_utc).count()
        valid_leads = db.query(Lead).filter(
            Lead.created_at >= start_utc,
            Lead.created_at <= end_utc,
            Lead.is_hiring == True
        ).count()
        invalid_leads = db.query(Lead).filter(
            Lead.created_at >= start_utc,
            Lead.created_at <= end_utc,
            Lead.is_hiring == False
        ).count()
        
        # Pitches dispatched today (status SENT and sent_at within today)
        sent_count = db.query(Lead).filter(
            Lead.sent_at >= start_utc,
            Lead.sent_at <= end_utc
        ).count()
        
        # Client inbound replies received today
        reply_count = db.query(EmailThread).filter(
            EmailThread.created_at >= start_utc,
            EmailThread.created_at <= end_utc,
            EmailThread.direction == "INBOUND"
        ).count()
        
        # User requested exact format:
        # 8thNov.2026
        # total leads: 8
        # valid leads: 7
        # invalid leads: 1
        # message send to user: 2
        # reply back by user: 0
        formatted_message = (
            f"{formatted_date}\n"
            f"total leads: {total_leads}\n"
            f"valid leads: {valid_leads}\n"
            f"invalid leads: {invalid_leads}\n"
            f"message send to user: {sent_count}\n"
            f"reply back by user: {reply_count}"
        )
        
        return {
            "date": formatted_date,
            "total_leads": total_leads,
            "valid_leads": valid_leads,
            "invalid_leads": invalid_leads,
            "message_send_to_user": sent_count,
            "reply_back_by_user": reply_count,
            "formatted_message": formatted_message
        }
    finally:
        if should_close:
            db.close()

async def send_whatsapp_message(message: str, phone: Optional[str] = None) -> Tuple[bool, str]:
    """
    Sends a WhatsApp message via CallMeBot API or Twilio.
    Also sends an email backup copy to EMAIL_USER.
    """
    target_phone = phone or settings.WHATSAPP_PHONE_NUMBER or "918280716327"
    # Clean phone: ensure 91 prefix for 10-digit Indian numbers
    clean_phone = target_phone.replace("+", "").replace("-", "").replace(" ", "").strip()
    if len(clean_phone) == 10 and not clean_phone.startswith("91"):
        clean_phone = f"91{clean_phone}"

    callmebot_key = settings.CALLMEBOT_API_KEY.strip()
    meta_token = settings.META_WHATSAPP_TOKEN.strip()
    meta_phone_id = settings.META_PHONE_NUMBER_ID.strip()
    success = False
    status_msg = ""

    # 1. Try Meta Official WhatsApp Business Cloud API
    if meta_token and meta_phone_id:
        try:
            url = f"https://graph.facebook.com/v21.0/{meta_phone_id}/messages"
            headers = {
                "Authorization": f"Bearer {meta_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": clean_phone,
                "type": "text",
                "text": {"preview_url": False, "body": message}
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code in [200, 201]:
                    success = True
                    status_msg = f"Dispatched to WhatsApp Business (+{clean_phone}) via Meta Cloud API"
                    logger.info(status_msg)
                else:
                    status_msg = f"Meta WhatsApp error (HTTP {res.status_code}): {res.text[:120]}"
                    logger.warning(status_msg)
        except Exception as me:
            status_msg = f"Meta WhatsApp connection failed: {me}"
            logger.error(status_msg)

    # 2. Try CallMeBot WhatsApp Gateway (Works seamlessly on personal & WhatsApp Business)
    elif callmebot_key:
        try:
            encoded_text = urllib.parse.quote(message)
            url = f"https://api.callmebot.com/whatsapp.php?phone=+{clean_phone}&text={encoded_text}&apikey={callmebot_key}"
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(url)
                if res.status_code == 200 and "error" not in res.text.lower():
                    success = True
                    status_msg = f"Dispatched to WhatsApp (+{clean_phone}) via CallMeBot"
                    logger.info(status_msg)
                else:
                    status_msg = f"CallMeBot error (HTTP {res.status_code}): {res.text[:120]}"
                    logger.warning(status_msg)
        except Exception as e:
            status_msg = f"CallMeBot connection failed: {e}"
            logger.error(status_msg)

    # 3. Try Twilio if credentials present
    elif settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_WHATSAPP_NUMBER:
        try:
            twilio_url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
            auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            data = {
                "From": f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}",
                "To": f"whatsapp:+{clean_phone}",
                "Body": message
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(twilio_url, auth=auth, data=data)
                if res.status_code in [200, 201]:
                    success = True
                    status_msg = f"Dispatched to WhatsApp (+{clean_phone}) via Twilio"
                else:
                    status_msg = f"Twilio error (HTTP {res.status_code}): {res.text[:120]}"
        except Exception as te:
            status_msg = f"Twilio dispatch failed: {te}"
    else:
        status_msg = "CALLMEBOT_API_KEY not configured. WhatsApp ready - activate free CallMeBot key or use 1-click WhatsApp link."
        logger.info(status_msg)

    # 3. Always dispatch an automated email copy to admin Gmail as guaranteed delivery backup!
    if settings.EMAIL_USER:
        try:
            await send_native_email_async(
                recipient_email=settings.EMAIL_USER,
                subject=f"Daily AutoLead AI Report: {message.splitlines()[0]}",
                body_text=f"Hello,\n\nHere is your daily AutoLead AI activity summary:\n\n{message}\n\nTarget WhatsApp: +{clean_phone}\nDelivery Status: {status_msg}\n\nBest regards,\nAutoLead AI System"
            )
            logger.info(f"Daily report email copy delivered to {settings.EMAIL_USER}")
        except Exception as me:
            logger.warning(f"Could not deliver email report backup: {me}")

    # Log to SystemLog in DB
    try:
        db = SessionLocal()
        log = SystemLog(
            level="SUCCESS" if success else "INFO",
            module="NOTIFIER",
            message=f"WhatsApp Report: {status_msg}",
            details=message
        )
        db.add(log)
        db.commit()
        db.close()
    except Exception:
        pass

    return success, status_msg

async def generate_and_send_daily_report(phone: Optional[str] = None) -> Dict[str, Any]:
    """Generates today's report and triggers WhatsApp delivery."""
    metrics = generate_daily_metrics()
    success, status_info = await send_whatsapp_message(metrics["formatted_message"], phone=phone)
    metrics["whatsapp_sent"] = success
    metrics["whatsapp_status"] = status_info
    
    # Generate 1-click WhatsApp web redirect link
    encoded_text = urllib.parse.quote(metrics["formatted_message"])
    target_phone = phone or settings.WHATSAPP_PHONE_NUMBER or "918280716327"
    clean_phone = target_phone.replace("+", "").replace("-", "").replace(" ", "").strip()
    if len(clean_phone) == 10 and not clean_phone.startswith("91"):
        clean_phone = f"91{clean_phone}"
    metrics["whatsapp_direct_url"] = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"
    
    return metrics

