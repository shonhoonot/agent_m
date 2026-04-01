"""
Supabase-д суурилсан хэрэглэгч бүрийн санах ой (memory) удирдах систем.
Facebook PSID-ийг түлхүүр болгон ашиглана.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache

from supabase import create_client, Client

import config

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_client() -> Client:
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Profile operations ────────────────────────────────────────────────────────

def get_or_create_user(psid: str, name: str = "") -> dict:
    """Хэрэглэгчийн профайлыг авах буюу үүсгэх."""
    db = _get_client()
    res = db.table("user_profiles").select("*").eq("psid", psid).limit(1).execute()

    if res.data:
        user = res.data[0]
        # Нэр шинэчлэх
        if name and not user.get("name"):
            db.table("user_profiles").update({"name": name, "updated_at": _now()}).eq("psid", psid).execute()
            user["name"] = name
    else:
        user = {
            "psid": psid,
            "name": name,
            "phone": "",
            "last_service": "",
            "appointment_count": 0,
            "is_new_lead": True,
            "created_at": _now(),
            "updated_at": _now(),
        }
        db.table("user_profiles").insert(user).execute()

    return {
        "psid": user["psid"],
        "name": user.get("name") or "",
        "phone": user.get("phone") or "",
        "last_service": user.get("last_service") or "",
        "appointment_count": user.get("appointment_count") or 0,
        "is_new_lead": bool(user.get("is_new_lead", True)),
    }


def update_user_profile(psid: str, **kwargs) -> None:
    """Хэрэглэгчийн мэдээллийг шинэчлэх."""
    db = _get_client()
    kwargs["updated_at"] = _now()
    # Хэрэглэгч байхгүй бол үүсгэх
    res = db.table("user_profiles").select("psid").eq("psid", psid).limit(1).execute()
    if not res.data:
        db.table("user_profiles").insert({"psid": psid, **kwargs}).execute()
    else:
        db.table("user_profiles").update(kwargs).eq("psid", psid).execute()


def mark_lead_notified(psid: str) -> None:
    """Telegram-д мэдэгдэл явуулсан болохыг тэмдэглэх."""
    update_user_profile(psid, is_new_lead=False)


def increment_appointment_count(psid: str, service_type: str = "") -> None:
    """Захиалгын тоог нэмэгдүүлэх."""
    db = _get_client()
    res = db.table("user_profiles").select("appointment_count").eq("psid", psid).limit(1).execute()
    current = res.data[0]["appointment_count"] if res.data else 0
    updates: dict = {"appointment_count": (current or 0) + 1, "updated_at": _now()}
    if service_type:
        updates["last_service"] = service_type
    db.table("user_profiles").update(updates).eq("psid", psid).execute()


# ─── Conversation history ──────────────────────────────────────────────────────

def save_message(psid: str, role: str, content: str) -> None:
    """Яриаг хадгалах."""
    db = _get_client()
    db.table("conversation_messages").insert({
        "psid": psid,
        "role": role,
        "content": content,
        "created_at": _now(),
    }).execute()


def get_conversation_history(psid: str, limit: int = 10) -> list[dict]:
    """Хэрэглэгчийн сүүлийн N мессежийг авах."""
    db = _get_client()
    res = (
        db.table("conversation_messages")
        .select("role, content")
        .eq("psid", psid)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(reversed(res.data)) if res.data else []


def clear_conversation_history(psid: str) -> None:
    """Хэрэглэгчийн яриаг цэвэрлэх."""
    _get_client().table("conversation_messages").delete().eq("psid", psid).execute()


def build_memory_context(psid: str) -> str:
    """Agent-д өгөх memory context string үүсгэх."""
    user = get_or_create_user(psid)
    parts = []
    if user["name"]:
        parts.append(f"Хэрэглэгчийн нэр: {user['name']}")
    if user["phone"]:
        parts.append(f"Утасны дугаар: {user['phone']}")
    if user["appointment_count"] > 0:
        parts.append(f"Нийт захиалга: {user['appointment_count']}")
    if user["last_service"]:
        parts.append(f"Сүүлийн үйлчилгээ: {user['last_service']}")
    return "\n".join(parts) if parts else ""
