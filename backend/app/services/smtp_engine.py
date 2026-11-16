import smtplib
import ssl
import email.utils
import datetime
import random
import asyncio
import logging
import pytz
import dns.resolver
import httpx
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional, Tuple

from app.config import settings
from app.models import AppSetting, SystemLog
from app.database import SessionLocal

logger = logging.getLogger(__name__)

def get_smtp_credentials() -> Dict[str, Any]:
    """Retrieve SMTP & HTTPS email settings from database overrides, falling back to .env settings."""
    smtp_user = settings.EMAIL_USER
    smtp_pass = settings.EMAIL_APP_PASSWORD
    smtp_host = settings.SMTP_HOST
    smtp_port = settings.SMTP_PORT
    sender_name = settings.SENDER_NAME
    brevo_api_key = settings.BREVO_API_KEY
    resend_api_key = settings.RESEND_API_KEY

    try:
        db = SessionLocal()
        u = db.query(AppSetting).filter(AppSetting.key == "email_user").first()
        p = db.query(AppSetting).filter(AppSetting.key == "email_app_password").first()
        h = db.query(AppSetting).filter(AppSetting.key == "smtp_host").first()
        prt = db.query(AppSetting).filter(AppSetting.key == "smtp_port").first()
        s = db.query(AppSetting).filter(AppSetting.key == "sender_name").first()
        b = db.query(AppSetting).filter(AppSetting.key == "brevo_api_key").first()
        r = db.query(AppSetting).filter(AppSetting.key == "resend_api_key").first()
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
        if b and b.value and b.value.strip():
            brevo_api_key = b.value.strip()
        if r and r.value and r.value.strip():
            resend_api_key = r.value.strip()
    except Exception as e:
        logger.warning(f"Error fetching SMTP DB settings: {e}")

    return {
        "user": smtp_user,
        "password": smtp_pass.replace(" ", "") if smtp_pass else "",
        "host": smtp_host,
        "port": smtp_port,
        "sender_name": sender_name,
        "brevo_api_key": brevo_api_key,
        "resend_api_key": resend_api_key
    }

def test_smtp_connection() -> Tuple[bool, str]:
    """
    Tests email sending configuration:
    1. If BREVO_API_KEY is configured -> Tests Brevo HTTPS API (Port 443)
    2. If RESEND_API_KEY is configured -> Tests Resend HTTPS API (Port 443)
    3. Else -> Tests direct SMTP connection to smtp.gmail.com (Ports 465/587)
    """
    creds = get_smtp_credentials()

    if creds.get("brevo_api_key"):
        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.get("https://api.brevo.com/v3/account", headers={"api-key": creds["brevo_api_key"].strip()})
                if res.status_code == 200:
                    info = res.json()
                    email_acct = info.get("email", creds.get("user", "Unknown"))
                    return True, f"Brevo HTTPS API authenticated successfully (Account: {email_acct}). Cloud port 465/587 blocks bypassed!"
                else:
                    return False, f"Brevo API error ({res.status_code}): {res.text[:200]}"
        except Exception as e:
            return False, f"Brevo HTTPS connection error: {str(e)}"

    if creds.get("resend_api_key"):
        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.get("https://api.resend.com/api-keys", headers={"Authorization": f"Bearer {creds['resend_api_key'].strip()}"})
                if res.status_code == 200:
                    return True, "Resend HTTPS API authenticated successfully. Cloud port 465/587 blocks bypassed!"
                else:
                    return False, f"Resend API error ({res.status_code}): {res.text[:200]}"
        except Exception as e:
            return False, f"Resend HTTPS connection error: {str(e)}"

    if not creds["user"] or not creds["password"]:
        return False, "SMTP credentials missing: Please provide EMAIL_USER and EMAIL_APP_PASSWORD, or configure BREVO_API_KEY / RESEND_API_KEY."

    try:
        if creds["port"] == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(creds["host"], creds["port"], context=context, timeout=10) as server:
                server.login(creds["user"], creds["password"])
                return True, f"Successfully authenticated direct SMTP connection to {creds['host']}:{creds['port']} as {creds['user']}"
        else:
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

def build_html_content(body_text: str) -> str:
    """Builds clean, responsive HTML email styling."""
    body_html_formatted = body_text.replace("\n\n", "</p><p style='margin: 0 0 16px 0;'>").replace("\n", "<br/>")
    return f"""<!DOCTYPE html>
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

    part_text = MIMEText(body_text, "plain", "utf-8")
    part_html = MIMEText(build_html_content(body_text), "html", "utf-8")

    msg.attach(part_text)
    msg.attach(part_html)

    return msg, message_id

def verify_email_domain_has_mx(email_address: str) -> Tuple[bool, str]:
    """
    Validates that the recipient domain has active, deliverable DNS MX records.
    Catches Null MX (RFC 7505) and non-existent domains BEFORE attempting send.
    Protects sender reputation from bounce backs.
    """
    if not email_address or "@" not in email_address:
        return False, "Invalid email format (missing @)"

    parts = email_address.strip().split("@")
    if len(parts) != 2 or not parts[1]:
        return False, "Malformed email address"

    domain = parts[1].lower()

    if domain.endswith(".placeholder") or "reddit-contact" in domain or "weworkremotely" in domain:
        return False, "Placeholder address is not a deliverable mailbox"

    try:
        answers = dns.resolver.resolve(domain, 'MX', lifetime=5)
        for rdata in answers:
            exchange = str(rdata.exchange).strip('.')
            if not exchange or exchange == '.':
                return False, f"Domain '{domain}' has Null MX (does not receive email according to RFC 7505)"
            return True, f"Valid MX record found: {exchange}"
        return False, f"Domain '{domain}' has no MX records"
    except dns.resolver.NXDOMAIN:
        return False, f"Domain '{domain}' does not exist (NXDOMAIN)"
    except dns.resolver.NoAnswer:
        return False, f"Domain '{domain}' has no MX records"
    except dns.resolver.Timeout:
        logger.warning(f"DNS lookup timed out for {domain}; proceeding cautiously")
        return True, "DNS lookup timed out"
    except Exception as e:
        logger.warning(f"DNS resolution error for {domain}: {e}")
        return False, f"DNS lookup failed: {str(e)}"

async def send_via_brevo_https(
    recipient_email: str,
    subject: str,
    body_text: str,
    in_reply_to: Optional[str] = None,
    creds: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str, Optional[str]]:
    """Dispatches email via Brevo's HTTPS REST API over port 443 (immune to cloud SMTP port blocks)."""
    if not creds:
        creds = get_smtp_credentials()

    api_key = creds.get("brevo_api_key")
    if not api_key:
        return False, "BREVO_API_KEY is not configured.", None

    sender_email = creds.get("user") or "5yearcodepro.dev@gmail.com"
    sender_name = creds.get("sender_name") or "Alex Rivera"

    headers = {
        "api-key": api_key.strip(),
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email
        },
        "to": [{"email": recipient_email}],
        "subject": subject,
        "htmlContent": build_html_content(body_text),
        "textContent": body_text
    }

    if in_reply_to:
        payload["headers"] = {
            "In-Reply-To": in_reply_to,
            "References": in_reply_to
        }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post("https://api.brevo.com/v3/smtp/email", headers=headers, json=payload)
            if resp.status_code in [200, 201, 202]:
                data = resp.json()
                msg_id = data.get("messageId") or f"<brevo-{datetime.datetime.utcnow().timestamp()}@{sender_email.split('@')[-1]}>"
                logger.info(f"Successfully dispatched email via Brevo HTTPS API to {recipient_email} (Msg ID: {msg_id})")
                return True, f"Dispatched email via Brevo HTTPS API to {recipient_email}", msg_id
            else:
                err_text = resp.text
                logger.error(f"Brevo API error ({resp.status_code}): {err_text}")
                return False, f"Brevo API Error ({resp.status_code}): {err_text[:200]}", None
    except Exception as e:
        logger.error(f"Brevo HTTP request failed: {e}")
        return False, f"Brevo connection error: {str(e)}", None

async def send_via_resend_https(
    recipient_email: str,
    subject: str,
    body_text: str,
    in_reply_to: Optional[str] = None,
    creds: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str, Optional[str]]:
    """Dispatches email via Resend's HTTPS REST API over port 443 (immune to cloud SMTP port blocks)."""
    if not creds:
        creds = get_smtp_credentials()

    api_key = creds.get("resend_api_key")
    if not api_key:
        return False, "RESEND_API_KEY is not configured.", None

    sender_email = creds.get("user") or "onboarding@resend.dev"
    sender_name = creds.get("sender_name") or "Alex Rivera"

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json"
    }

    payload = {
        "from": f"{sender_name} <{sender_email}>",
        "to": [recipient_email],
        "subject": subject,
        "html": build_html_content(body_text),
        "text": body_text
    }

    if in_reply_to:
        payload["headers"] = {
            "In-Reply-To": in_reply_to,
            "References": in_reply_to
        }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post("https://api.resend.com/emails", headers=headers, json=payload)
            if resp.status_code in [200, 201, 202]:
                data = resp.json()
                msg_id = data.get("id") or f"<resend-{datetime.datetime.utcnow().timestamp()}@{sender_email.split('@')[-1]}>"
                logger.info(f"Successfully dispatched email via Resend HTTPS API to {recipient_email} (ID: {msg_id})")
                return True, f"Dispatched email via Resend HTTPS API to {recipient_email}", msg_id
            else:
                err_text = resp.text
                logger.error(f"Resend API error ({resp.status_code}): {err_text}")
                return False, f"Resend API Error ({resp.status_code}): {err_text[:200]}", None
    except Exception as e:
        logger.error(f"Resend HTTP request failed: {e}")
        return False, f"Resend connection error: {str(e)}", None

def send_native_email_sync(
    recipient_email: str,
    subject: str,
    body_text: str,
    in_reply_to: Optional[str] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Synchronous SMTP dispatch via standard library smtplib.
    Used for local development or providers allowing direct port 465/587 egress.
    """
    creds = get_smtp_credentials()

    if not creds["user"] or not creds["password"]:
        return False, "SMTP credentials missing: Please provide EMAIL_USER and EMAIL_APP_PASSWORD.", None

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
    """
    Universal Email Dispatcher:
    - If BREVO_API_KEY is configured: Dispatches via Brevo HTTPS REST API (Port 443, Railway safe)
    - If RESEND_API_KEY is configured: Dispatches via Resend HTTPS REST API (Port 443, Railway safe)
    - Fallback: Native smtplib (Ports 465 / 587) for local testing
    """
    if not recipient_email or "@" not in recipient_email:
        return False, f"Invalid recipient email: '{recipient_email}'", None

    # 1. Reject placeholder addresses immediately
    if recipient_email.endswith(".placeholder") or "@reddit-contact." in recipient_email or "weworkremotely" in recipient_email:
        return False, f"Cannot dispatch: {recipient_email} is a placeholder address (no real email provided)", None

    # 2. Perform DNS MX Verification
    has_mx, mx_reason = verify_email_domain_has_mx(recipient_email)
    if not has_mx:
        logger.warning(f"Aborting dispatch to {recipient_email}: {mx_reason}")
        return False, f"Undeliverable recipient domain: {mx_reason}", None

    creds = get_smtp_credentials()

    # 3. Check for HTTPS API providers first (Brevo / Resend)
    if creds.get("brevo_api_key"):
        return await send_via_brevo_https(recipient_email, subject, body_text, in_reply_to, creds)
    elif creds.get("resend_api_key"):
        return await send_via_resend_https(recipient_email, subject, body_text, in_reply_to, creds)

    # 4. Fallback to native smtplib in executor
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
        return True

async def anti_ban_delay():
    """Anti-ban throttle: 45 to 90 seconds random delay between consecutive bulk emails."""
    min_sec = settings.EMAIL_THROTTLE_MIN_SEC
    max_sec = settings.EMAIL_THROTTLE_MAX_SEC
    delay = random.randint(min_sec, max_sec)
    logger.info(f"Anti-ban throttle: sleeping for {delay} seconds before next dispatch...")
    await asyncio.sleep(delay)
