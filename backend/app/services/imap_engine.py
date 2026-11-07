import imaplib
import email
import email.header
import datetime
import logging
import asyncio
import re
from typing import Dict, Any, List, Optional, Tuple

from app.config import settings
from app.models import Lead, EmailThread, AppSetting, SystemLog
from app.database import SessionLocal
from app.services.smtp_engine import get_smtp_credentials, send_native_email_async
from app.services.gemini_engine import analyze_inbound_reply

logger = logging.getLogger(__name__)

def get_imap_credentials() -> Dict[str, Any]:
    """Retrieve IMAP configuration from DB overrides or .env."""
    creds = get_smtp_credentials()
    imap_host = settings.IMAP_HOST
    imap_port = settings.IMAP_PORT
    auto_reply_mode = settings.AUTO_REPLY_MODE

    try:
        db = SessionLocal()
        h = db.query(AppSetting).filter(AppSetting.key == "imap_host").first()
        p = db.query(AppSetting).filter(AppSetting.key == "imap_port").first()
        m = db.query(AppSetting).filter(AppSetting.key == "auto_reply_mode").first()
        db.close()

        if h and h.value:
            imap_host = h.value.strip()
        if p and p.value:
            imap_port = int(p.value)
        if m and m.value:
            auto_reply_mode = m.value.strip()
    except Exception as e:
        logger.warning(f"Error reading IMAP settings: {e}")

    return {
        "user": creds["user"],
        "password": creds["password"],
        "host": imap_host,
        "port": imap_port,
        "auto_reply_mode": auto_reply_mode
    }

def test_imap_connection() -> Tuple[bool, str]:
    """
    Directly tests IMAP SSL connection to imap.gmail.com:993 with credentials.
    """
    creds = get_imap_credentials()
    if not creds["user"] or not creds["password"]:
        return False, "IMAP credentials missing: Please provide EMAIL_USER and EMAIL_APP_PASSWORD."

    try:
        mail = imaplib.IMAP4_SSL(creds["host"], creds["port"], timeout=10)
        mail.login(creds["user"], creds["password"])
        status, _ = mail.select("INBOX", readonly=True)
        mail.logout()
        if status == "OK":
            return True, f"Successfully authenticated direct IMAP connection to {creds['host']}:{creds['port']} as {creds['user']}"
        return False, f"Connected to IMAP, but failed to select INBOX. Status: {status}"
    except imaplib.IMAP4.error as e:
        return False, f"Gmail IMAP Authentication Failed: {str(e)}"
    except Exception as e:
        return False, f"IMAP Connection Failed: {str(e)}"

def decode_header_value(val: Optional[str]) -> str:
    """Decodes MIME encoded email header fields."""
    if not val:
        return ""
    decoded_fragments = email.header.decode_header(val)
    parts = []
    for fragment, encoding in decoded_fragments:
        if isinstance(fragment, bytes):
            try:
                parts.append(fragment.decode(encoding or "utf-8", errors="replace"))
            except Exception:
                parts.append(fragment.decode("latin1", errors="replace"))
        else:
            parts.append(str(fragment))
    return "".join(parts)

def parse_email_message(raw_bytes: bytes) -> Dict[str, Any]:
    """Extracts metadata and body content from raw RFC 822 email bytes."""
    msg = email.message_from_bytes(raw_bytes)

    subject = decode_header_value(msg.get("Subject"))
    sender = decode_header_value(msg.get("From"))
    message_id = msg.get("Message-ID", "")
    in_reply_to = msg.get("In-Reply-To", "")
    references = msg.get("References", "")

    # Clean sender to just email address
    clean_sender = sender
    if "<" in sender and ">" in sender:
        clean_sender = sender.split("<")[1].split(">")[0].strip()

    body_text = ""
    body_html = ""

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get("Content-Disposition"))
            if "attachment" not in cdispo:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        decoded = payload.decode(charset, errors="replace")
                    except Exception:
                        decoded = payload.decode("latin1", errors="replace")

                    if ctype == "text/plain" and not body_text:
                        body_text = decoded
                    elif ctype == "text/html" and not body_html:
                        body_html = decoded
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body_text = payload.decode(charset, errors="replace")

    return {
        "subject": subject,
        "sender": clean_sender,
        "full_sender": sender,
        "message_id": message_id,
        "in_reply_to": in_reply_to,
        "references": references,
        "body_text": body_text.strip(),
        "body_html": body_html.strip()
    }

async def poll_imap_inbox() -> Dict[str, Any]:
    """
    Module D: Native IMAP poller service.
    Polls Gmail INBOX for unread messages, matches outgoing Message-IDs
    or client email addresses, analyzes replies with Gemini, and records thread.
    """
    creds = get_imap_credentials()

    if not creds["user"] or not creds["password"]:
        return {
            "status": "skipped",
            "message": "Gmail credentials not set; waiting for configuration in Settings."
        }

    db = SessionLocal()
    matched_replies = 0

    try:
        # Run blocking IMAP operations in threadpool
        loop = asyncio.get_running_loop()

        def fetch_unread_emails_sync():
            items = []
            mail = imaplib.IMAP4_SSL(creds["host"], creds["port"], timeout=15)
            mail.login(creds["user"], creds["password"])
            mail.select("INBOX")
            # Search for UNSEEN emails
            status, response = mail.search(None, "UNSEEN")
            if status == "OK" and response[0]:
                email_ids = response[0].split()
                # Inspect up to 20 recent unseen emails
                for e_id in email_ids[-20:]:
                    f_status, data = mail.fetch(e_id, "(RFC822)")
                    if f_status == "OK" and data and isinstance(data[0], tuple):
                        raw_email = data[0][1]
                        parsed = parse_email_message(raw_email)
                        items.append(parsed)
            mail.logout()
            return items

        unread_emails = await loop.run_in_executor(None, fetch_unread_emails_sync)

        for incoming in unread_emails:
            sender_lower = incoming.get("sender", "").lower()
            subject_lower = incoming.get("subject", "").lower()
            full_sender_lower = incoming.get("full_sender", "").lower()

            is_bounce = (
                "mailer-daemon" in sender_lower
                or "postmaster" in sender_lower
                or "mailer-daemon" in full_sender_lower
                or "mail delivery subsystem" in full_sender_lower
                or "address not found" in subject_lower
                or "delivery status notification" in subject_lower
                or "undelivered mail" in subject_lower
                or "returned mail" in subject_lower
                or "failure notice" in subject_lower
            )

            # 1. Match by In-Reply-To or References matching lead's message_id
            matched_lead = None
            ref = incoming.get("in_reply_to") or incoming.get("references")
            if ref:
                matched_lead = db.query(Lead).filter(Lead.message_id.isnot(None), Lead.message_id.contains(ref.strip())).first()

            # If bounce, extract failed recipient address from bounce message body
            if not matched_lead and is_bounce:
                body = incoming.get("body_text", "")
                found_emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', body)
                for em in found_emails:
                    if not any(x in em.lower() for x in ["mailer-daemon", "googlemail", "gmail.com"]):
                        matched_lead = db.query(Lead).filter(Lead.email == em).first()
                        if matched_lead:
                            break

            # 2. Match by Sender Email (only if not a bounce notification!)
            if not matched_lead and not is_bounce and incoming.get("sender"):
                matched_lead = db.query(Lead).filter(Lead.email == incoming["sender"]).first()

            if matched_lead:
                if is_bounce:
                    logger.warning(f"Lead #{matched_lead.id} ({matched_lead.email}) bounced: {incoming['subject']}")
                    matched_lead.status = "BOUNCED"
                    matched_lead.updated_at = datetime.datetime.utcnow()

                    bounce_thread = EmailThread(
                        lead_id=matched_lead.id,
                        direction="INBOUND",
                        sender=incoming["sender"],
                        recipient=creds["user"] or "me",
                        subject=f"Delivery Failure: {incoming['subject']}",
                        body_text=incoming.get("body_text", "")[:600],
                        message_id=incoming.get("message_id"),
                        in_reply_to=incoming.get("in_reply_to"),
                        status="BOUNCED",
                        created_at=datetime.datetime.utcnow()
                    )
                    db.add(bounce_thread)

                    log = SystemLog(
                        level="WARNING",
                        module="IMAP",
                        message=f"Bounced email detected for Lead #{matched_lead.id} ({matched_lead.email})",
                        details=incoming["subject"]
                    )
                    db.add(log)
                    db.commit()
                    continue

                # Update lead status to REPLIED
                matched_lead.status = "REPLIED"
                matched_lead.updated_at = datetime.datetime.utcnow()

                # Run Gemini Reply Engine
                lead_context = f"Title: {matched_lead.title}\nPitch sent: {matched_lead.email_body}"
                analysis = await analyze_inbound_reply(
                    lead_context=lead_context,
                    inbound_subject=incoming["subject"],
                    inbound_body=incoming["body_text"]
                )

                sentiment = analysis.get("sentiment", "INTERESTED")
                draft = analysis.get("auto_reply_draft", "")

                thread_status = "NEEDS_REVIEW"
                
                # Check auto-reply mode
                if creds["auto_reply_mode"] == "autonomous" and sentiment in ["INTERESTED", "SCHEDULING"]:
                    # Auto-send reply via native SMTP!
                    reply_subj = f"Re: {incoming['subject']}" if not incoming['subject'].lower().startswith("re:") else incoming['subject']
                    ok, msg_res, reply_msg_id = await send_native_email_async(
                        recipient_email=matched_lead.email,
                        subject=reply_subj,
                        body_text=draft,
                        in_reply_to=incoming.get("message_id")
                    )
                    if ok:
                        thread_status = "AUTO_REPLIED"
                        # Record outbound auto-reply thread
                        outbound_thread = EmailThread(
                            lead_id=matched_lead.id,
                            direction="OUTBOUND",
                            sender=creds["user"],
                            recipient=matched_lead.email,
                            subject=reply_subj,
                            body_text=draft,
                            message_id=reply_msg_id,
                            in_reply_to=incoming.get("message_id"),
                            status="AUTO_REPLIED",
                            created_at=datetime.datetime.utcnow()
                        )
                        db.add(outbound_thread)

                # Record inbound thread
                inbound_thread = EmailThread(
                    lead_id=matched_lead.id,
                    direction="INBOUND",
                    sender=incoming["sender"],
                    recipient=creds["user"],
                    subject=incoming["subject"],
                    body_text=incoming["body_text"],
                    body_html=incoming.get("body_html"),
                    message_id=incoming.get("message_id"),
                    in_reply_to=incoming.get("in_reply_to"),
                    sentiment=sentiment,
                    auto_reply_draft=draft,
                    status=thread_status,
                    created_at=datetime.datetime.utcnow()
                )
                db.add(inbound_thread)
                matched_replies += 1

        db.commit()

        if matched_replies > 0:
            log = SystemLog(
                level="SUCCESS",
                module="IMAP",
                message=f"IMAP Listener processed {len(unread_emails)} unseen emails, matched {matched_replies} client replies."
            )
            db.add(log)
            db.commit()

        return {
            "status": "success",
            "unseen_count": len(unread_emails),
            "matched_replies": matched_replies
        }

    except Exception as e:
        logger.error(f"IMAP poll error: {e}")
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

