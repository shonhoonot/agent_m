"""
FastAPI сервер — Facebook Messenger Webhook
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse

import config
from agent import chat
from memory.user_memory import get_or_create_user

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Dental Clinic Messenger Bot", version="1.0.0")


# ─── Facebook Graph API helper ────────────────────────────────────────────────

async def send_fb_message(recipient_id: str, text: str) -> None:
    """Facebook Messenger-р мессеж илгээх."""
    if not config.FB_PAGE_ACCESS_TOKEN:
        logger.warning("FB_PAGE_ACCESS_TOKEN тохируулаагүй.")
        return

    url = "https://graph.facebook.com/v19.0/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }
    headers = {"Content-Type": "application/json"}
    params = {"access_token": config.FB_PAGE_ACCESS_TOKEN}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers=headers, params=params)
            if resp.status_code != 200:
                logger.error(f"FB мессеж илгээхэд алдаа: {resp.status_code} — {resp.text}")
    except Exception as e:
        logger.error(f"FB API алдаа: {e}")


async def send_typing_on(recipient_id: str) -> None:
    """Бичиж байгаа индикатор харуулах."""
    if not config.FB_PAGE_ACCESS_TOKEN:
        return
    url = "https://graph.facebook.com/v19.0/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "sender_action": "typing_on",
    }
    params = {"access_token": config.FB_PAGE_ACCESS_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json=payload, params=params)
    except Exception:
        pass


async def get_user_profile(psid: str) -> dict:
    """Facebook Graph API-аас хэрэглэгчийн нэр авах."""
    if not config.FB_PAGE_ACCESS_TOKEN:
        return {}
    url = f"https://graph.facebook.com/v19.0/{psid}"
    params = {
        "fields": "first_name,last_name",
        "access_token": config.FB_PAGE_ACCESS_TOKEN,
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "name": f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
                }
    except Exception:
        pass
    return {}


# ─── Signature verification ───────────────────────────────────────────────────

def verify_fb_signature(payload: bytes, signature_header: str) -> bool:
    """Facebook webhook signature шалгах."""
    if not config.FB_APP_SECRET:
        return True  # Dev mode — skip
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        config.FB_APP_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)


# ─── Background message processor ─────────────────────────────────────────────

async def process_message(psid: str, text: str, user_name: str) -> None:
    """Хэрэглэгчийн мессежийг боловсруулж хариу илгээх."""
    await send_typing_on(psid)
    try:
        # LangChain agent дуудах (sync → run in thread)
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: chat(psid=psid, user_message=text, user_name=user_name),
        )
        # None эсвэл буруу төрлийг шалгах
        if not response or not isinstance(response, str):
            response = "Уучлаарай, хариу боловсруулахад алдаа гарлаа."
        response = response.strip()
        if not response:
            response = "Уучлаарай, хариу боловсруулахад алдаа гарлаа."
        logger.info(f"Agent response (psid={psid}): {response[:100]}")
        chunks = _split_message(response, max_length=1900)
        for chunk in chunks:
            await send_fb_message(psid, chunk)
    except Exception as e:
        logger.error(f"process_message алдаа (psid={psid}): {e}")
        await send_fb_message(
            psid,
            f"Уучлаарай, техникийн алдаа гарлаа. {config.CLINIC_PHONE} дугаарт залгана уу.",
        )


def _split_message(text: str, max_length: int = 1900) -> list[str]:
    if len(text) <= max_length:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = max_length
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    return chunks


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/webhook")
async def fb_webhook_verify(
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
):
    """Facebook Webhook баталгаажуулалт."""
    # FastAPI query params нь underscore-г dash болгодог тул manually авах
    return await _verify_handler(hub_mode, hub_verify_token, hub_challenge)


@app.get("/webhook/")
async def fb_webhook_verify_slash(request: Request):
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    return await _verify_handler(mode, token, challenge)


async def _verify_handler(mode, token, challenge):
    if mode == "subscribe" and token == config.FB_VERIFY_TOKEN:
        logger.info("Facebook Webhook баталгаажлаа.")
        return PlainTextResponse(challenge or "")
    logger.warning(f"Webhook verify failed: mode={mode!r}, token={token!r}, expected={config.FB_VERIFY_TOKEN!r}")
    raise HTTPException(status_code=403, detail=f"Verification failed: mode={mode}, token_match={token == config.FB_VERIFY_TOKEN}")


@app.post("/webhook")
async def fb_webhook_events(request: Request, background_tasks: BackgroundTasks):
    return await _handle_webhook(request, background_tasks)


@app.post("/webhook/")
async def fb_webhook_events_slash(request: Request, background_tasks: BackgroundTasks):
    return await _handle_webhook(request, background_tasks)


async def _handle_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()

    # Signature шалгах
    sig = request.headers.get("X-Hub-Signature-256", "")
    if sig and not verify_fb_signature(body, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if data.get("object") != "page":
        return Response(status_code=404)

    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender_id = messaging.get("sender", {}).get("id")
            if not sender_id:
                continue

            # Зөвхөн энгийн мессежийг боловсруулах
            message = messaging.get("message", {})
            if message.get("is_echo"):
                continue  # Bot өөрийн мессежийг алгасах

            text = message.get("text", "").strip()
            if not text:
                # Зураг/файл ирсэн бол
                if message.get("attachments"):
                    text = "[Зураг/файл илгээлээ]"
                else:
                    continue

            # Postback (товч дарсан)
            postback = messaging.get("postback", {})
            if postback:
                text = postback.get("payload", postback.get("title", "Сайн уу"))

            # Хэрэглэгчийн нэр авах (background-д)
            user_profile = await get_user_profile(sender_id)
            user_name = user_profile.get("name", "")

            logger.info(f"Мессеж ирлээ: psid={sender_id}, text={text[:50]}")

            # Background-д боловсруулах (200-г шуурхай буцаах)
            background_tasks.add_task(process_message, sender_id, text, user_name)

    return Response(status_code=200)


@app.get("/health")
async def health():
    return {"status": "ok", "clinic": config.CLINIC_NAME}


@app.get("/")
async def root():
    return {
        "service": f"{config.CLINIC_NAME} — Messenger Bot",
        "version": "1.0.0",
        "endpoints": {
            "webhook": "/webhook",
            "health": "/health",
        },
    }


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=config.PORT, reload=False)
