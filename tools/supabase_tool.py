"""
Supabase tool — цаг захиалга бүртгэх, шалгах, цуцлах.
Google Calendar + Google Sheets-ийг орлоно.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, date

import pytz
from langchain.tools import tool

import config
from memory.user_memory import _get_client

UB_TZ = pytz.timezone("Asia/Ulaanbaatar")


def _parse_work_hours():
    h_start, m_start = map(int, config.CLINIC_WORKING_HOURS_START.split(":"))
    h_end, m_end = map(int, config.CLINIC_WORKING_HOURS_END.split(":"))
    return (h_start, m_start), (h_end, m_end)


def _get_booked_slots(date_str: str) -> list[str]:
    """Тухайн өдрийн захиалагдсан цагуудыг авах."""
    db = _get_client()
    res = (
        db.table("appointments")
        .select("time_str")
        .eq("date_str", date_str)
        .neq("status", "Цуцлагдсан")
        .execute()
    )
    return [r["time_str"] for r in (res.data or [])]


@tool
def get_available_slots(date_str: str) -> str:
    """
    Тодорхой өдрийн боломжит цагийн слотуудыг буцаана.
    date_str: YYYY-MM-DD форматтай огноо (жишээ: 2025-04-10).
    Буцаах утга: боломжит цагуудын жагсаалт.
    """
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now(UB_TZ).date()
        if target < today:
            return json.dumps({"error": "Өнгөрсөн огноо сонгогдлоо."})
        if target.weekday() == 6:  # Ням гараг
            return json.dumps({"date": date_str, "available_slots": [], "message": "Ням гараг амарна."})

        (h_start, m_start), (h_end, m_end) = _parse_work_hours()
        slot_duration = timedelta(minutes=config.CLINIC_SLOT_DURATION_MINUTES)

        start_dt = datetime(target.year, target.month, target.day, h_start, m_start)
        end_dt = datetime(target.year, target.month, target.day, h_end, m_end)

        booked = set(_get_booked_slots(date_str))

        available = []
        current = start_dt
        now = datetime.now(UB_TZ).replace(tzinfo=None)
        while current + slot_duration <= end_dt:
            slot_str = current.strftime("%H:%M")
            # Өнөөдөр бол өнгөрсөн цагийг алгасах
            if target == today and current <= now:
                current += slot_duration
                continue
            if slot_str not in booked:
                available.append(slot_str)
            current += slot_duration

        if not available:
            return json.dumps({"date": date_str, "available_slots": [], "message": "Тухайн өдөр боломжит цаг байхгүй."})
        return json.dumps({"date": date_str, "available_slots": available})

    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_next_available_days(days_ahead: int = 7) -> str:
    """
    Өнөөдрөөс эхлэн боломжит цагтай өдрүүдийг хайна.
    days_ahead: хэдэн өдрийг шалгах (default 7).
    """
    try:
        today = datetime.now(UB_TZ).date()
        weekday_mn = ["Даваа", "Мягмар", "Лхагва", "Пүрэв", "Баасан", "Бямба", "Ням"]
        result = []
        for i in range(1, days_ahead + 1):
            check_date = today + timedelta(days=i)
            if check_date.weekday() == 6:
                continue
            date_str = check_date.strftime("%Y-%m-%d")
            slots_data = json.loads(get_available_slots.invoke(date_str))
            slots = slots_data.get("available_slots", [])
            if slots:
                result.append({
                    "date": date_str,
                    "weekday": weekday_mn[check_date.weekday()],
                    "first_slot": slots[0],
                    "total_slots": len(slots),
                })
        return json.dumps({"available_days": result})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def book_appointment(
    patient_name: str,
    patient_phone: str,
    date_str: str,
    time_str: str,
    service_type: str = "Шүдний үзлэг",
    facebook_psid: str = "",
    notes: str = "",
) -> str:
    """
    Цаг захиалгыг Supabase-д бүртгэнэ.
    Параметрүүд:
      - patient_name: Өвчтөний нэр
      - patient_phone: Утасны дугаар
      - date_str: YYYY-MM-DD огноо
      - time_str: HH:MM цаг
      - service_type: Үйлчилгээний төрөл
      - facebook_psid: Facebook хэрэглэгчийн ID
      - notes: Нэмэлт тэмдэглэл
    """
    try:
        db = _get_client()
        # Давхардал шалгах
        existing = (
            db.table("appointments")
            .select("id")
            .eq("date_str", date_str)
            .eq("time_str", time_str)
            .neq("status", "Цуцлагдсан")
            .execute()
        )
        if existing.data:
            return json.dumps({"success": False, "message": f"{date_str} {time_str} цаг аль хэдийн захиалагдсан байна. Өөр цаг сонгоно уу."})

        record = {
            "patient_name": patient_name,
            "patient_phone": patient_phone,
            "date_str": date_str,
            "time_str": time_str,
            "service_type": service_type,
            "facebook_psid": facebook_psid,
            "notes": notes,
            "status": "Баталгаажсан",
        }
        res = db.table("appointments").insert(record).execute()
        apt_id = res.data[0]["id"] if res.data else "?"

        return json.dumps({
            "success": True,
            "appointment_id": apt_id,
            "message": (
                f"✅ Цаг амжилттай захиалагдлаа!\n"
                f"📅 Огноо: {date_str} {time_str}\n"
                f"🦷 Үйлчилгээ: {service_type}\n"
                f"👤 Нэр: {patient_name}\n"
                f"📞 Утас: {patient_phone}"
            ),
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@tool
def get_patient_appointments(facebook_psid: str) -> str:
    """
    Хэрэглэгчийн захиалгуудыг харуулна.
    facebook_psid: Facebook хэрэглэгчийн PSID.
    """
    try:
        db = _get_client()
        res = (
            db.table("appointments")
            .select("id, date_str, time_str, service_type, status, notes")
            .eq("facebook_psid", facebook_psid)
            .order("date_str", desc=True)
            .limit(5)
            .execute()
        )
        if not res.data:
            return json.dumps({"appointments": [], "message": "Захиалга олдсонгүй."})
        return json.dumps({"appointments": res.data})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def cancel_appointment(appointment_id: str, facebook_psid: str) -> str:
    """
    Захиалгыг цуцална.
    appointment_id: Захиалгын ID (get_patient_appointments-аас авна).
    facebook_psid: Баталгаажуулахад хэрэглэнэ.
    """
    try:
        db = _get_client()
        res = (
            db.table("appointments")
            .select("id, facebook_psid, status, date_str, time_str")
            .eq("id", appointment_id)
            .limit(1)
            .execute()
        )
        if not res.data:
            return json.dumps({"success": False, "message": "Захиалга олдсонгүй."})
        apt = res.data[0]
        if apt["facebook_psid"] != facebook_psid:
            return json.dumps({"success": False, "message": "Та энэ захиалгыг цуцлах эрхгүй."})
        if apt["status"] == "Цуцлагдсан":
            return json.dumps({"success": False, "message": "Захиалга аль хэдийн цуцлагдсан байна."})

        db.table("appointments").update({"status": "Цуцлагдсан"}).eq("id", appointment_id).execute()
        return json.dumps({
            "success": True,
            "message": f"❌ {apt['date_str']} {apt['time_str']}-ийн захиалга цуцлагдлаа.",
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
