import logging
import httpx
from typing import Dict, Any, Tuple, Optional

from app.config import settings
from app.database import SessionLocal
from app.models import SystemLog
from app.services.whatsapp_notifier import generate_daily_metrics

logger = logging.getLogger(__name__)

async def send_telegram_message(
    message: str,
    chat_id: Optional[str] = None,
    bot_token: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Sends a message via official Telegram Bot API (100% Lifetime Free).
    API Endpoint: https://api.telegram.org/bot<TOKEN>/sendMessage
    """
    token = (bot_token or settings.TELEGRAM_BOT_TOKEN or "").strip()
    target_chat_id = (chat_id or settings.TELEGRAM_CHAT_ID or "").strip()

    if not token:
        msg = "TELEGRAM_BOT_TOKEN not configured in .env"
        logger.warning(msg)
        return False, msg

    if not target_chat_id:
        # Try auto-discovering chat_id from recent bot updates
        discovered_id = await auto_discover_chat_id(token)
        if discovered_id:
            target_chat_id = discovered_id
            logger.info(f"Auto-discovered Telegram chat_id: {target_chat_id}")
        else:
            msg = "TELEGRAM_CHAT_ID not configured. Please send /start to your bot on Telegram."
            logger.warning(msg)
            return False, msg

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": message
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                status_info = f"Dispatched report to Telegram chat {target_chat_id}"
                logger.info(status_info)
                
                # Log to SystemLog
                try:
                    db = SessionLocal()
                    db.add(SystemLog(
                        level="SUCCESS",
                        module="TELEGRAM",
                        message=status_info,
                        details=message
                    ))
                    db.commit()
                    db.close()
                except Exception:
                    pass
                
                return True, status_info
            else:
                err_desc = data.get("description", resp.text[:120])
                msg = f"Telegram API error: {err_desc}"
                logger.error(msg)
                return False, msg
    except Exception as e:
        msg = f"Telegram connection failed: {e}"
        logger.error(msg)
        return False, msg

async def auto_discover_chat_id(bot_token: Optional[str] = None) -> Optional[str]:
    """
    Queries getUpdates to find the user's chat_id automatically
    after they send /start to their bot.
    """
    token = (bot_token or settings.TELEGRAM_BOT_TOKEN or "").strip()
    if not token:
        return None

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            data = resp.json()
            if data.get("ok") and data.get("result"):
                # Get latest message
                for update in reversed(data["result"]):
                    msg = update.get("message") or update.get("channel_post")
                    if msg and "chat" in msg:
                        return str(msg["chat"]["id"])
    except Exception as e:
        logger.warning(f"Error checking Telegram updates: {e}")
    return None

async def generate_and_send_telegram_report(
    chat_id: Optional[str] = None,
    bot_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates daily lead metrics and dispatches report to Telegram.
    Exact format requested:
    8thNov.2026
    total leads: 8
    valid leads: 7
    invalid leads: 1
    message send to user: 2
    reply back by user: 0
    """
    metrics = generate_daily_metrics()
    success, status_info = await send_telegram_message(
        message=metrics["formatted_message"],
        chat_id=chat_id,
        bot_token=bot_token
    )
    metrics["telegram_sent"] = success
    metrics["telegram_status"] = status_info
    return metrics
