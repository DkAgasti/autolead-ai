import logging
import json
import urllib.request
import urllib.error
import asyncio
from typing import Dict, Any, Tuple, Optional

from app.config import settings
from app.database import SessionLocal
from app.models import SystemLog
from app.services.whatsapp_notifier import generate_daily_metrics

logger = logging.getLogger(__name__)

def _sync_telegram_post(url: str, payload: dict) -> Tuple[bool, dict]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return True, res_data
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        try:
            return False, json.loads(err_body)
        except Exception:
            return False, {"description": err_body}
    except Exception as e:
        return False, {"description": str(e)}

def _sync_telegram_get(url: str) -> Tuple[bool, dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AutoLeadAI/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return True, res_data
    except Exception as e:
        return False, {"description": str(e)}

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

    loop = asyncio.get_running_loop()
    ok, data = await loop.run_in_executor(None, _sync_telegram_post, url, payload)

    if ok and data.get("ok"):
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
        err_desc = data.get("description", "Unknown error")
        msg = f"Telegram API error: {err_desc}"
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
    loop = asyncio.get_running_loop()
    ok, data = await loop.run_in_executor(None, _sync_telegram_get, url)

    if ok and data.get("ok") and data.get("result"):
        # Look for messages in updates
        for update in reversed(data["result"]):
            msg = update.get("message") or update.get("channel_post")
            if msg and "chat" in msg:
                return str(msg["chat"]["id"])
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

