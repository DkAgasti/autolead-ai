import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), index=True, default="Reddit")  # Reddit / LinkedIn / Web
    source_url = Column(String(500), unique=True, index=True, nullable=True)
    title = Column(String(500), nullable=False)
    raw_text = Column(Text, nullable=False)
    author_id = Column(String(100), nullable=True)
    email = Column(String(255), index=True, nullable=True)
    website_url = Column(String(500), nullable=True)
    detected_country = Column(String(100), default="United States")
    timezone = Column(String(100), default="America/New_York")
    
    # Status: 'RAW', 'ANALYZED', 'FILTERED_OUT', 'SCHEDULED', 'SENT', 'REPLIED'
    status = Column(String(50), default="RAW", index=True)
    
    # Gemini 2.5 Flash Analyzed fields
    is_hiring = Column(Boolean, nullable=True)
    lead_name = Column(String(150), nullable=True)
    pain_points = Column(Text, nullable=True)  # JSON-encoded array of points
    audit_summary = Column(Text, nullable=True)
    subject_line = Column(String(300), nullable=True)
    email_body = Column(Text, nullable=True)
    
    # Scheduling & Delivery
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    message_id = Column(String(255), index=True, nullable=True)  # RFC 2822 Message-ID
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    threads = relationship("EmailThread", back_populates="lead", cascade="all, delete-orphan", order_by="EmailThread.created_at.asc()")

class EmailThread(Base):
    __tablename__ = "email_threads"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    direction = Column(String(20), nullable=False)  # 'OUTBOUND' or 'INBOUND'
    sender = Column(String(255), nullable=False)
    recipient = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body_text = Column(Text, nullable=False)
    body_html = Column(Text, nullable=True)
    message_id = Column(String(255), index=True, nullable=True)
    in_reply_to = Column(String(255), index=True, nullable=True)
    
    # Inbound Gemini classification
    sentiment = Column(String(50), nullable=True)  # 'INTERESTED', 'SCHEDULING', 'NOT_INTERESTED', 'OBJECTION', 'NEUTRAL'
    auto_reply_draft = Column(Text, nullable=True)
    status = Column(String(50), default="RECEIVED")  # 'SENT', 'RECEIVED', 'NEEDS_REVIEW', 'AUTO_REPLIED'
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    lead = relationship("Lead", back_populates="threads")

class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(20), default="INFO")  # INFO, WARNING, ERROR, SUCCESS
    module = Column(String(50), index=True)     # SCRAPER, GEMINI, SMTP, IMAP, SCHEDULER
    message = Column(Text, nullable=False)
    details = Column(Text, nullable=True)       # JSON string or stacktrace
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
