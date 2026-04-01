"""
Telegram notification tool — шинэ lead ирэхэд мэдэгдэл илгээх
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

import httpx

import config

logger = logging.getLogger(__name__)


async def _send_telegram_message(text: str) -> bool:
    """Telegram Bot API руу message илгээх."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_LEAD_CHAT_ID:
        logger.warning("Telegram config байхгүй — мэдэгдэл илгээгдсэнгүй.")
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_LEAD_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Telegram илгээхэд алдаа: {e}")
        return False


def send_telegram_sync(text: str) -> bool:
    """Sync wrapper — FastAPI sync context-д ашиглах."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _send_telegram_message(text))
                return future.result(timeout=15)
        else:
            return loop.run_until_complete(_send_telegram_message(text))
    except Exception as e:
        logger.error(f"Telegram sync wrapper алдаа: {e}")
        return False


def notify_new_lead(
    facebook_psid: str,
    user_name: str,
    first_message: str,
) -> None:
    """Шинэ хэрэглэгч Facebook-аар мессеж илгээхэд Telegram-д мэдэгдэх."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = (
        f"🦷 <b>Шинэ Lead — {config.CLINIC_NAME}</b>\n\n"
        f"👤 <b>Нэр:</b> {user_name}\n"
        f"🆔 <b>PSID:</b> <code>{facebook_psid}</code>\n"
        f"💬 <b>Анхны мессеж:</b>\n{first_message}\n\n"
        f"🕐 <b>Цаг:</b> {now}"
    )
    send_telegram_sync(text)


def notify_new_appointment(
    patient_name: str,
    patient_phone: str,
    date_str: str,
    time_str: str,
    service_type: str,
    facebook_psid: str,
) -> None:
    """Шинэ захиалга бүртгэгдэхэд Telegram-д мэдэгдэх."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = (
        f"✅ <b>Шинэ Захиалга — {config.CLINIC_NAME}</b>\n\n"
        f"👤 <b>Өвчтөн:</b> {patient_name}\n"
        f"📞 <b>Утас:</b> {patient_phone}\n"
        f"🗓 <b>Цаг:</b> {date_str} {time_str}\n"
        f"🦷 <b>Үйлчилгээ:</b> {service_type}\n"
        f"🆔 <b>Facebook PSID:</b> <code>{facebook_psid}</code>\n\n"
        f"🕐 <b>Бүртгэгдсэн:</b> {now}"
    )
    send_telegram_sync(text)


def notify_cancellation(
    patient_name: str,
    record_id: str,
    date_str: str,
) -> None:
    """Захиалга цуцлагдахад Telegram-д мэдэгдэх."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = (
        f"❌ <b>Захиалга Цуцлагдлаа — {config.CLINIC_NAME}</b>\n\n"
        f"👤 <b>Өвчтөн:</b> {patient_name}\n"
        f"🆔 <b>Захиалгын ID:</b> <code>{record_id}</code>\n"
        f"🗓 <b>Огноо:</b> {date_str}\n"
        f"🕐 <b>Цаг:</b> {now}"
    )
    send_telegram_sync(text)
