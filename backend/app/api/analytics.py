import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Lead, EmailThread, SystemLog
from app.schemas import AnalyticsSummary

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("", response_model=AnalyticsSummary)
def get_analytics(db: Session = Depends(get_db)):
    """Computes real-time lead pipeline analytics and reply rates."""
    total_leads = db.query(Lead).count()

    today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    scraped_today = db.query(Lead).filter(Lead.created_at >= today_start).count()

    # Valid leads = hiring confirmed or analyzed
    valid_leads = db.query(Lead).filter(Lead.status.in_(["ANALYZED", "SCHEDULED", "SENT", "REPLIED"])).count()
    
    # Sent emails
    emails_dispatched = db.query(Lead).filter(Lead.status.in_(["SENT", "REPLIED"])).count()

    # Replies
    replies_received = db.query(Lead).filter(Lead.status == "REPLIED").count()

    reply_rate = 0.0
    if emails_dispatched > 0:
        reply_rate = round((replies_received / emails_dispatched) * 100, 1)

    # Status distribution
    status_counts = {}
    for st in ["RAW", "ANALYZED", "FILTERED_OUT", "SCHEDULED", "SENT", "REPLIED"]:
        status_counts[st] = db.query(Lead).filter(Lead.status == st).count()

    # Source distribution
    source_rows = db.query(Lead.source, func.count(Lead.id)).group_by(Lead.source).all()
    source_counts = {src: count for src, count in source_rows}

    # Recent activity logs
    logs = db.query(SystemLog).order_by(SystemLog.created_at.desc()).limit(8).all()
    recent_activity = [
        {
            "id": l.id,
            "level": l.level,
            "module": l.module,
            "message": l.message,
            "time": l.created_at.strftime("%H:%M:%S")
        }
        for l in logs
    ]

    return AnalyticsSummary(
        total_leads=total_leads,
        scraped_today=scraped_today,
        valid_leads=valid_leads,
        emails_dispatched=emails_dispatched,
        replies_received=replies_received,
        reply_rate=reply_rate,
        status_counts=status_counts,
        source_counts=source_counts,
        recent_activity=recent_activity
    )

