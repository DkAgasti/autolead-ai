import json
import datetime
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import Lead, EmailThread, SystemLog
from app.schemas import LeadOut, LeadCreate, LeadUpdate, SendEmailRequest, ReplySendRequest
from app.services.website_auditor import audit_website
from app.services.gemini_engine import analyze_lead_with_gemini
from app.services.smtp_engine import send_native_email_async, get_smtp_credentials
from app.services.scheduler import is_autonomous_outreach_enabled, scheduled_outbound_queue_dispatcher

router = APIRouter(prefix="/api/leads", tags=["leads"])

@router.get("", response_model=List[LeadOut])
def list_leads(
    status: Optional[str] = Query(None, description="Filter by status"),
    source: Optional[str] = Query(None, description="Filter by source (Reddit, LinkedIn, Web)"),
    country: Optional[str] = Query(None, description="Filter by country"),
    search: Optional[str] = Query(None, description="Search keyword in title, text, or author"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = db.query(Lead)

    if status and status != "ALL":
        query = query.filter(Lead.status == status)
    if source and source != "ALL":
        query = query.filter(Lead.source == source)
    if country and country != "ALL":
        query = query.filter(Lead.detected_country == country)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Lead.title.ilike(search_filter)) |
            (Lead.raw_text.ilike(search_filter)) |
            (Lead.author_id.ilike(search_filter)) |
            (Lead.email.ilike(search_filter))
        )

    leads = query.order_by(Lead.id.desc()).offset(offset).limit(limit).all()
    return leads

@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead

@router.post("", response_model=LeadOut)
def create_lead(lead_in: LeadCreate, db: Session = Depends(get_db)):
    lead = Lead(
        source=lead_in.source,
        source_url=lead_in.source_url,
        title=lead_in.title,
        raw_text=lead_in.raw_text,
        author_id=lead_in.author_id,
        email=lead_in.email,
        website_url=lead_in.website_url,
        detected_country=lead_in.detected_country or "United States",
        timezone=lead_in.timezone or "America/New_York",
        status="RAW"
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead

@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(lead_id: int, lead_in: LeadUpdate, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if lead_in.title is not None:
        lead.title = lead_in.title
    if lead_in.email is not None:
        lead.email = lead_in.email
    if lead_in.website_url is not None:
        lead.website_url = lead_in.website_url
    if lead_in.status is not None:
        lead.status = lead_in.status
    if lead_in.subject_line is not None:
        lead.subject_line = lead_in.subject_line
    if lead_in.email_body is not None:
        lead.email_body = lead_in.email_body
    if lead_in.scheduled_at is not None:
        lead.scheduled_at = lead_in.scheduled_at

    lead.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(lead)
    return lead

@router.delete("/{lead_id}")
def delete_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(lead)
    db.commit()
    return {"status": "success", "message": f"Lead {lead_id} deleted"}

@router.post("/{lead_id}/analyze", response_model=LeadOut)
async def analyze_single_lead(lead_id: int, db: Session = Depends(get_db)):
    """
    Triggers Gemini 2.5 Flash Engine:
    - Runs website technical audit if URL exists
    - Filters intent (is_hiring)
    - Extracts pain points and deliverables
    - Generates 100-130 word personalized cold pitch
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    audit_result = None
    if lead.website_url:
        audit_result = await audit_website(lead.website_url)

    result = await analyze_lead_with_gemini(
        title=lead.title,
        raw_text=lead.raw_text,
        website_url=lead.website_url,
        audit_data=audit_result
    )

    lead.is_hiring = result["is_hiring"]
    lead.lead_name = result["lead_name"]
    lead.pain_points = json.dumps(result["pain_points"])
    lead.audit_summary = result["audit_summary"]
    lead.subject_line = result["subject_line"]
    lead.email_body = result["email_body"]

    if lead.is_hiring:
        if not lead.email:
            lead.status = "NEEDS_EMAIL"
        elif is_autonomous_outreach_enabled():
            lead.status = "SCHEDULED"
            lead.scheduled_at = datetime.datetime.utcnow()
            asyncio.create_task(scheduled_outbound_queue_dispatcher())
        else:
            lead.status = "ANALYZED"
    else:
        lead.status = "FILTERED_OUT"

    lead.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(lead)
    return lead

@router.post("/analyze-all-raw")
async def bulk_analyze_raw_leads(db: Session = Depends(get_db)):
    """Bulk analyze all leads currently in RAW status."""
    raw_leads = db.query(Lead).filter(Lead.status == "RAW").all()
    autonomous = is_autonomous_outreach_enabled()
    count = 0
    for lead in raw_leads:
        audit_res = None
        if lead.website_url:
            audit_res = await audit_website(lead.website_url)
        res = await analyze_lead_with_gemini(lead.title, lead.raw_text, lead.website_url, audit_res)
        lead.is_hiring = res["is_hiring"]
        lead.lead_name = res["lead_name"]
        lead.pain_points = json.dumps(res["pain_points"])
        lead.audit_summary = res["audit_summary"]
        lead.subject_line = res["subject_line"]
        lead.email_body = res["email_body"]
        if res["is_hiring"]:
            if autonomous:
                lead.status = "SCHEDULED"
                lead.scheduled_at = datetime.datetime.utcnow()
            else:
                lead.status = "ANALYZED"
        else:
            lead.status = "FILTERED_OUT"
        lead.updated_at = datetime.datetime.utcnow()
        count += 1
    db.commit()

    if autonomous and count > 0:
        asyncio.create_task(scheduled_outbound_queue_dispatcher())

    return {"status": "success", "analyzed_count": count}

@router.post("/{lead_id}/schedule", response_model=LeadOut)
def schedule_lead(lead_id: int, db: Session = Depends(get_db)):
    """Puts the lead into the recipient timezone queue (SCHEDULED)."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    lead.status = "SCHEDULED"
    lead.scheduled_at = datetime.datetime.utcnow()
    lead.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(lead)
    return lead

@router.post("/{lead_id}/send-now")
async def send_lead_now(
    lead_id: int,
    req: Optional[SendEmailRequest] = None,
    db: Session = Depends(get_db)
):
    """
    1-Click Action Center: Approve and send pitch immediately via direct SMTP.
    Uses smtplib over Port 465 SSL / 587 TLS with Google App Password.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    recipient = (req.recipient_override if req and req.recipient_override else None) or lead.email
    if not recipient:
        raise HTTPException(status_code=400, detail="Lead has no recipient email address. Please provide one.")

    subject = (req.subject if req and req.subject else None) or lead.subject_line or f"Quick note regarding {lead.title[:30]}"
    body = (req.body if req and req.body else None) or lead.email_body or "Hi there, wanted to reach out regarding your project."

    creds = get_smtp_credentials()

    success, msg_info, message_id = await send_native_email_async(
        recipient_email=recipient,
        subject=subject,
        body_text=body
    )

    if not success:
        raise HTTPException(status_code=500, detail=f"SMTP Send Failed: {msg_info}")

    lead.status = "SENT"
    lead.sent_at = datetime.datetime.utcnow()
    lead.message_id = message_id
    lead.subject_line = subject
    lead.email_body = body
    lead.updated_at = datetime.datetime.utcnow()

    # Create thread entry
    thread = EmailThread(
        lead_id=lead.id,
        direction="OUTBOUND",
        sender=creds["user"] or "sender@gmail.com",
        recipient=recipient,
        subject=subject,
        body_text=body,
        message_id=message_id,
        status="SENT",
        created_at=datetime.datetime.utcnow()
    )
    db.add(thread)

    log = SystemLog(
        level="SUCCESS",
        module="SMTP",
        message=f"Dispatched pitch to {recipient} (Lead #{lead.id})",
        details=f"Message-ID: {message_id}"
    )
    db.add(log)
    db.commit()
    db.refresh(lead)

    return {
        "status": "success",
        "message": msg_info,
        "message_id": message_id,
        "lead": LeadOut.from_orm(lead)
    }

@router.post("/{lead_id}/discard", response_model=LeadOut)
def discard_lead(lead_id: int, db: Session = Depends(get_db)):
    """1-Click Discard from Action Center."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.status = "FILTERED_OUT"
    lead.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(lead)
    return lead

@router.post("/{lead_id}/reply")
async def send_followup_reply(
    lead_id: int,
    req: ReplySendRequest,
    db: Session = Depends(get_db)
):
    """Sends a follow-up or replies to a client's response thread."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.email:
        raise HTTPException(status_code=400, detail="Lead does not have an email address.")

    creds = get_smtp_credentials()
    subject = req.subject or f"Re: {lead.subject_line or 'Our conversation'}"

    # Find the latest inbound message for in_reply_to header
    latest_inbound = db.query(EmailThread).filter(
        EmailThread.lead_id == lead.id,
        EmailThread.direction == "INBOUND"
    ).order_by(EmailThread.created_at.desc()).first()

    in_reply_to_val = latest_inbound.message_id if latest_inbound else lead.message_id

    success, msg_info, message_id = await send_native_email_async(
        recipient_email=lead.email,
        subject=subject,
        body_text=req.reply_body,
        in_reply_to=in_reply_to_val
    )

    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to send reply: {msg_info}")

    # Mark the latest review thread as resolved
    if latest_inbound and latest_inbound.status == "NEEDS_REVIEW":
        latest_inbound.status = "AUTO_REPLIED"

    thread = EmailThread(
        lead_id=lead.id,
        direction="OUTBOUND",
        sender=creds["user"] or "sender@gmail.com",
        recipient=lead.email,
        subject=subject,
        body_text=req.reply_body,
        message_id=message_id,
        in_reply_to=in_reply_to_val,
        status="SENT",
        created_at=datetime.datetime.utcnow()
    )
    db.add(thread)
    db.commit()

    return {"status": "success", "message_id": message_id}

