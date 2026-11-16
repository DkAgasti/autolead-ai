from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.database import get_db
from app.models import AppSetting
from app.config import settings
from app.schemas import AppSettingsSchema
from app.services.smtp_engine import test_smtp_connection, get_smtp_credentials
from app.services.imap_engine import test_imap_connection, get_imap_credentials

router = APIRouter(prefix="/api/settings", tags=["settings"])

def get_db_setting(db: Session, key: str, default: str = "") -> str:
    s = db.query(AppSetting).filter(AppSetting.key == key).first()
    return s.value if s and s.value is not None else default

def set_db_setting(db: Session, key: str, val: str):
    s = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not s:
        s = AppSetting(key=key, value=val)
        db.add(s)
    else:
        s.value = val
    db.commit()

@router.get("", response_model=AppSettingsSchema)
def get_settings_values(db: Session = Depends(get_db)):
    """Returns current system configuration, masking sensitive passwords for safety."""
    api_key = get_db_setting(db, "gemini_api_key", settings.GEMINI_API_KEY)
    masked_key = ""
    if api_key:
        masked_key = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"

    email_user = get_db_setting(db, "email_user", settings.EMAIL_USER)
    email_app_pw = get_db_setting(db, "email_app_password", settings.EMAIL_APP_PASSWORD)
    masked_pw = "••••••••••••••••" if email_app_pw else ""

    brevo_key = get_db_setting(db, "brevo_api_key", settings.BREVO_API_KEY)
    masked_brevo = brevo_key[:4] + "..." + brevo_key[-4:] if len(brevo_key) > 8 else ("***" if brevo_key else "")

    resend_key = get_db_setting(db, "resend_api_key", settings.RESEND_API_KEY)
    masked_resend = resend_key[:4] + "..." + resend_key[-4:] if len(resend_key) > 8 else ("***" if resend_key else "")

    return AppSettingsSchema(
        gemini_api_key=masked_key,
        email_user=email_user,
        email_app_password=masked_pw,
        brevo_api_key=masked_brevo,
        resend_api_key=masked_resend,
        smtp_host=get_db_setting(db, "smtp_host", settings.SMTP_HOST),
        smtp_port=int(get_db_setting(db, "smtp_port", str(settings.SMTP_PORT))),
        imap_host=get_db_setting(db, "imap_host", settings.IMAP_HOST),
        imap_port=int(get_db_setting(db, "imap_port", str(settings.IMAP_PORT))),
        sender_name=get_db_setting(db, "sender_name", settings.SENDER_NAME),
        portfolio_url=get_db_setting(db, "portfolio_url", settings.PORTFOLIO_URL),
        calendly_url=get_db_setting(db, "calendly_url", settings.CALENDLY_URL),
        auto_reply_mode=get_db_setting(db, "auto_reply_mode", settings.AUTO_REPLY_MODE),
        daily_scrape_time_ist=get_db_setting(db, "daily_scrape_time_ist", settings.DAILY_SCRAPE_TIME_IST),
        email_throttle_min_sec=int(get_db_setting(db, "email_throttle_min_sec", str(settings.EMAIL_THROTTLE_MIN_SEC))),
        email_throttle_max_sec=int(get_db_setting(db, "email_throttle_max_sec", str(settings.EMAIL_THROTTLE_MAX_SEC)))
    )

@router.post("")
def update_settings_values(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """Updates runtime configuration in the database settings table."""
    for key, val in payload.items():
        if val is None:
            continue
        # Avoid overwriting secrets with masked bullets or ellipsis
        if key in ["email_app_password", "gemini_api_key", "brevo_api_key", "resend_api_key"] and ("•••" in str(val) or "..." in str(val)):
            continue
        set_db_setting(db, key, str(val))
    return {"status": "success", "message": "Settings updated successfully"}

@router.post("/test-smtp")
def run_smtp_test():
    """Diagnostic button: Tests direct connection and login to smtp.gmail.com."""
    success, message = test_smtp_connection()
    if not success:
        return {"success": False, "message": message}
    return {"success": True, "message": message}

@router.post("/test-imap")
def run_imap_test():
    """Diagnostic button: Tests direct SSL connection and login to imap.gmail.com."""
    success, message = test_imap_connection()
    if not success:
        return {"success": False, "message": message}
    return {"success": True, "message": message}

