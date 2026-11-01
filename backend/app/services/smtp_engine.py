import smtplib
import ssl
import email.utils
import datetime
import random
import asyncio
import logging
import pytz
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional, Tuple

from app.config import settings
from app.models import AppSetting, SystemLog
from app.database import SessionLocal

logger = logging.getLogger(__name__)

def get_smtp_credentials() -> Dict[str, Any]:
    """Retrieve SMTP settings from database overrides, falling back to .env settings."""
    smtp_user = settings.EMAIL_USER
    smtp_pass = settings.EMAIL_APP_PASSWORD
    smtp_host = settings.SMTP_HOST
    smtp_port = settings.SMTP_PORT
    sender_name = settings.SENDER_NAME

    try:
        db = SessionLocal()
        u = db.query(AppSetting).filter(AppSetting.key == "email_user").first()
        p = db.query(AppSetting).filter(AppSetting.key == "email_app_password").first()
        h = db.query(AppSetting).filter(AppSetting.key == "smtp_host").first()
        prt = db.query(AppSetting).filter(AppSetting.key == "smtp_port").first()
        s = db.query(AppSetting).filter(AppSetting.key == "sender_name").first()
        db.close()

        if u and u.value and u.value.strip():
            smtp_user = u.value.strip()
        if p and p.value and p.value.strip():
            smtp_pass = p.value.strip()
        if h and h.value and h.value.strip():
            smtp_host = h.value.strip()
        if prt and prt.value:
            smtp_port = int(prt.value)
        if s and s.value and s.value.strip():
            sender_name = s.value.strip()
    except Exception as e:
        logger.warning(f"Error fetching SMTP DB settings: {e}")

    return {
        "user": smtp_user,
        "password": smtp_pass.replace(" ", ""),  # Remove whitespace often copied into 16-char app passwords
        "host": smtp_host,
        "port": smtp_port,
        "sender_name": sender_name
    }

def test_smtp_connection() -> Tuple[bool, str]:
    """
    Directly tests connection to smtp.gmail.com using standard smtplib.
    Returns (True, message) if successful or (False, error_details).
    """
    creds = get_smtp_credentials()
    if not creds["user"] or not creds["password"]:
        return False, "SMTP credentials missing: Please provide EMAIL_USER and EMAIL_APP_PASSWORD."

    try:
        if creds["port"] == 465:
            # SSL
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(creds["host"], creds["port"], context=context, timeout=10) as server:
                server.login(creds["user"], creds["password"])
                return True, f"Successfully authenticated direct SMTP connection to {creds['host']}:{creds['port']} as {creds['user']}"
        else:
            # TLS (587)
            with smtplib.SMTP(creds["host"], creds["port"], timeout=10) as server:
                server.ehlo()
                context = ssl.create_default_context()
                server.starttls(context=context)
                server.ehlo()
                server.login(creds["user"], creds["password"])
                return True, f"Successfully authenticated direct TLS connection to {creds['host']}:{creds['port']} as {creds['user']}"
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Gmail SMTP Authentication Failed (code {e.smtp_code}): Check your 16-character App Password. Error: {e.smtp_error.decode() if isinstance(e.smtp_error, bytes) else str(e.smtp_error)}"
    except Exception as e:
        return False, f"SMTP Connection Failed: {str(e)}"

def build_mime_email(
    sender_name: str,
    sender_email: str,
    recipient_email: str,
    subject: str,
    body_text: str,
    in_reply_to: Optional[str] = None
) -> Tuple[MIMEMultipart, str]:
    """
    Builds RFC 2822 compliant multi-part MIME email message
    with custom Message-ID, Date, HTML styling, and plain text fallback.
    """
    msg = MIMEMultipart("alternative")
    domain = sender_email.split("@")[-1] if "@" in sender_email else "gmail.com"
    message_id = email.utils.make_msgid(domain=domain)
    
    msg["Message-ID"] = message_id
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = recipient_email
    msg["Subject"] = subject

    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to

    # Plain text version
    part_text = MIMEText(body_text, "plain", "utf-8")
    
    # HTML version with clean modern styling
    body_html_formatted = body_text.replace("\n\n", "</p><p style='margin: 0 0 16px 0;'>").replace("\n", "<br/>")
    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      font-size: 15px;
      line-height: 1.6;
      color: #1f2937;
      background-color: #ffffff;
      margin: 0;
      padding: 16px;
    }}
    a {{
      color: #2563eb;
      text-decoration: underline;
    }}
  </style>
</head>
<body>
  <div style="max-width: 600px; margin: 0 auto;">
    <p style="margin: 0 0 16px 0;">{body_html_formatted}</p>
  </div>
</body>
</html>"""
    part_html = MIMEText(html_content, "html", "utf-8")

    msg.attach(part_text)
    msg.attach(part_html)

    return msg, message_id

def send_native_email_sync(
    recipient_email: str,
    subject: str,
    body_text: str,
    in_reply_to: Optional[str] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Synchronous SMTP dispatch via standard library smtplib.
    Returns (success: bool, status_message: str, message_id: str).
    """
    creds = get_smtp_credentials()

    if not creds["user"] or not creds["password"]:
        # If no credentials yet in testing, simulate and return mock Message-ID
        mock_id = email.utils.make_msgid(domain="gmail.com")
        return True, "Simulated send (credentials pending in Settings)", mock_id

    # If recipient has a placeholder domain, simulate safe delivery
    if recipient_email.endswith(".placeholder") or "@reddit-contact." in recipient_email:
        mock_id = email.utils.make_msgid(domain="gmail.com")
        return True, f"Simulated delivery to placeholder recipient {recipient_email}", mock_id

    try:
        msg, message_id = build_mime_email(
            sender_name=creds["sender_name"],
            sender_email=creds["user"],
            recipient_email=recipient_email,
            subject=subject,
            body_text=body_text,
            in_reply_to=in_reply_to
        )

        if creds["port"] == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(creds["host"], creds["port"], context=context, timeout=15) as server:
                server.login(creds["user"], creds["password"])
                server.sendmail(creds["user"], [recipient_email], msg.as_string())
        else:
            with smtplib.SMTP(creds["host"], creds["port"], timeout=15) as server:
                server.ehlo()
                context = ssl.create_default_context()
                server.starttls(context=context)
                server.ehlo()
                server.login(creds["user"], creds["password"])
                server.sendmail(creds["user"], [recipient_email], msg.as_string())

        return True, f"Dispatched email to {recipient_email}", message_id

    except Exception as e:
        logger.error(f"SMTP dispatch error to {recipient_email}: {e}")
        return False, str(e), None

async def send_native_email_async(
    recipient_email: str,
    subject: str,
    body_text: str,
    in_reply_to: Optional[str] = None
) -> Tuple[bool, str, Optional[str]]:
    """Runs synchronous smtplib in a thread pool to avoid blocking asyncio event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        send_native_email_sync,
        recipient_email,
        subject,
        body_text,
        in_reply_to
    )

def is_within_client_window(tz_str: str) -> bool:
    """
    Checks if current time in recipient's timezone is within
    the target outreach window: 9:30 AM to 11:00 AM.
    """
    try:
        tz = pytz.timezone(tz_str)
        client_time = datetime.datetime.now(tz)
        current_minutes = client_time.hour * 60 + client_time.minute
        # 9:30 AM = 570 mins, 11:00 AM = 660 mins
        return 570 <= current_minutes <= 660
    except Exception:
        # Default to True if timezone parsing fails
        return True

async def anti_ban_delay():
    """Anti-ban throttle: 45 to 90 seconds random delay between consecutive bulk emails."""
    min_sec = settings.EMAIL_THROTTLE_MIN_SEC
    max_sec = settings.EMAIL_THROTTLE_MAX_SEC
    delay = random.randint(min_sec, max_sec)
    logger.info(f"Anti-ban throttle: sleeping for {delay} seconds before next dispatch...")
    await asyncio.sleep(delay)

