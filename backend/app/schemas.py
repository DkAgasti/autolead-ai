from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

class LeadBase(BaseModel):
    source: str = "Reddit"
    source_url: Optional[str] = None
    title: str
    raw_text: str
    author_id: Optional[str] = None
    email: Optional[str] = None
    website_url: Optional[str] = None
    detected_country: Optional[str] = "United States"
    timezone: Optional[str] = "America/New_York"

class LeadCreate(LeadBase):
    pass

class LeadUpdate(BaseModel):
    title: Optional[str] = None
    email: Optional[str] = None
    website_url: Optional[str] = None
    status: Optional[str] = None
    subject_line: Optional[str] = None
    email_body: Optional[str] = None
    scheduled_at: Optional[datetime] = None

class EmailThreadOut(BaseModel):
    id: int
    lead_id: int
    direction: str
    sender: str
    recipient: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    message_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    sentiment: Optional[str] = None
    auto_reply_draft: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class LeadOut(LeadBase):
    id: int
    status: str
    is_hiring: Optional[bool] = None
    lead_name: Optional[str] = None
    pain_points: Optional[str] = None
    audit_summary: Optional[str] = None
    subject_line: Optional[str] = None
    email_body: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    message_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    threads: List[EmailThreadOut] = []

    class Config:
        from_attributes = True

class GeminiAnalysisResponse(BaseModel):
    is_hiring: bool
    lead_name: str
    pain_points: List[str]
    audit_summary: str
    subject_line: str
    email_body: str

class SendEmailRequest(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    recipient_override: Optional[str] = None

class ReplySendRequest(BaseModel):
    reply_body: str
    subject: Optional[str] = None

class AppSettingsSchema(BaseModel):
    gemini_api_key: Optional[str] = None
    email_user: Optional[str] = None
    email_app_password: Optional[str] = None
    brevo_api_key: Optional[str] = None
    resend_api_key: Optional[str] = None
    smtp_host: Optional[str] = "smtp.gmail.com"
    smtp_port: Optional[int] = 465
    imap_host: Optional[str] = "imap.gmail.com"
    imap_port: Optional[int] = 993
    sender_name: Optional[str] = "Alex Rivera"
    portfolio_url: Optional[str] = "https://alexrivera.dev"
    calendly_url: Optional[str] = "https://calendly.com/alexrivera/30min"
    auto_reply_mode: Optional[str] = "manual"
    daily_scrape_time_ist: Optional[str] = "10:00"
    email_throttle_min_sec: Optional[int] = 45
    email_throttle_max_sec: Optional[int] = 90

class AnalyticsSummary(BaseModel):
    total_leads: int
    scraped_today: int
    valid_leads: int
    emails_dispatched: int
    replies_received: int
    reply_rate: float
    status_counts: Dict[str, int]
    source_counts: Dict[str, int]
    recent_activity: List[Dict[str, Any]]

