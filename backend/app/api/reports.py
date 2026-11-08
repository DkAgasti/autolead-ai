from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.whatsapp_notifier import (
    generate_daily_metrics,
    send_whatsapp_message,
    generate_and_send_daily_report
)
from app.services.telegram_notifier import (
    generate_and_send_telegram_report,
    auto_discover_chat_id
)

router = APIRouter(prefix="/api/reports", tags=["Reports & Notifications"])

@router.get("/daily-summary")
def get_daily_summary(
    phone: Optional[str] = Query(None, description="Optional phone number override"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Returns today's lead generation & outreach metrics formatted for WhatsApp."""
    metrics = generate_daily_metrics(db=db)
    from app.config import settings
    import urllib.parse
    target_phone = phone or settings.WHATSAPP_PHONE_NUMBER or "918280716327"
    clean_phone = target_phone.replace("+", "").replace("-", "").replace(" ", "").strip()
    if len(clean_phone) == 10 and not clean_phone.startswith("91"):
        clean_phone = f"91{clean_phone}"
    
    encoded_text = urllib.parse.quote(metrics["formatted_message"])
    metrics["whatsapp_direct_url"] = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"
    metrics["target_phone"] = f"+{clean_phone}"
    metrics["has_callmebot_key"] = bool(settings.CALLMEBOT_API_KEY.strip())
    return metrics

@router.post("/send-whatsapp")
async def trigger_whatsapp_report(
    phone: Optional[str] = Query(None, description="Optional phone number override"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Generates today's report and immediately dispatches it to WhatsApp and Email."""
    result = await generate_and_send_daily_report(phone=phone)
    return {
        "status": "success",
        "message": result.get("whatsapp_status", "Report processed"),
        "metrics": result
    }

@router.get("/telegram-summary")
def get_telegram_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Returns today's lead generation & outreach metrics formatted for Telegram."""
    metrics = generate_daily_metrics(db=db)
    from app.config import settings
    metrics["has_bot_token"] = bool(settings.TELEGRAM_BOT_TOKEN.strip())
    metrics["has_chat_id"] = bool(settings.TELEGRAM_CHAT_ID.strip())
    metrics["chat_id"] = settings.TELEGRAM_CHAT_ID
    return metrics

@router.post("/send-telegram")
async def trigger_telegram_report(
    chat_id: Optional[str] = Query(None, description="Optional chat ID override"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Generates today's report and dispatches it directly to Telegram."""
    result = await generate_and_send_telegram_report(chat_id=chat_id)
    return {
        "status": "success" if result.get("telegram_sent") else "warning",
        "message": result.get("telegram_status", "Telegram processed"),
        "metrics": result
    }

@router.get("/auto-detect-telegram-chat")
async def detect_telegram_chat(token: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Auto-detects the user's chat_id when they send /start to their bot."""
    discovered = await auto_discover_chat_id(bot_token=token)
    if discovered:
        return {"status": "success", "chat_id": discovered}
    return {"status": "not_found", "message": "No recent messages found. Please send /start to your bot on Telegram first."}

