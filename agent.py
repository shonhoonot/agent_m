"""
LangChain Agent — шүдний эмнэлгийн цаг захиалах туслагч.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

import pytz
from langchain_anthropic import ChatAnthropic
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

import config
from tools.supabase_tool import (
    get_available_slots,
    get_next_available_days,
    book_appointment,
    get_patient_appointments,
    cancel_appointment,
)
from memory.user_memory import (
    get_or_create_user,
    save_message,
    get_conversation_history,
    build_memory_context,
    update_user_profile,
    mark_lead_notified,
    increment_appointment_count,
)
from tools.telegram_tool import notify_new_lead, notify_new_appointment, notify_cancellation

logger = logging.getLogger(__name__)

UB_TZ = pytz.timezone("Asia/Ulaanbaatar")

# ─── Бүх tool-уудыг нэгтгэх ──────────────────────────────────────────────────
ALL_TOOLS = [
    get_available_slots,
    get_next_available_days,
    book_appointment,
    get_patient_appointments,
    cancel_appointment,
]

# ─── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Та {clinic_name} шүдний эмнэлгийн цаг захиалах туслах AI юм.

📍 Хаяг: {clinic_address}
📞 Утас: {clinic_phone}
⏰ Ажиллах цаг: {working_hours_start} — {working_hours_end} (Даваа-Бямба)

Өнөөдрийн огноо: {today}

{memory_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🦷 ҮЙЛЧИЛГЭЭНҮҮД:
• Шүдний ерөнхий үзлэг — 30 мин
• Шүд цэвэрлэгээ (хальс авалт) — 30 мин
• Шүд өвдөлт / яаралтай үзлэг — 30 мин
• Шүд авалт — 30 мин
• Пломб тавих — 30-60 мин
• Имплант зөвлөгөө — 30 мин
• Шүдний сувилал (root canal) — 60 мин
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ДҮРЭМ:
1. Хэрэглэгчтэй МОНГОЛ хэлээр харилцана.
2. Эелдэг, хүндэтгэлтэй байна. "Та" гэж хэрэглэнэ.
3. Цаг захиалахаас өмнө заавал: нэр, утасны дугаар, үйлчилгээний төрөл асуух.
4. Боломжит цаг олоход get_available_slots эсвэл get_next_available_days ашиглах.
5. Цаг баталгаажуулахдаа: book_appointment ашиглах (facebook_psid параметрийг заавал дамжуулах).
6. Хэрэглэгч нэр/утас өгсөн бол memory-д автоматаар хадгалагдана.
7. Хэрэглэгч "захиалга харах" гэвэл get_patient_appointments ашиглах.
8. Хэрэглэгч "цуцлах" гэвэл эхлээд get_patient_appointments дуудаж ID авах, дараа cancel_appointment ашиглах.
9. Хэрэв мэдэхгүй зүйл асуувал: "{clinic_phone} дугаарт залгана уу" гэж хэлэх.
10. Хэрэглэгчийн нэрийг мэддэг бол харилцахдаа нэрийг нь ашиглах.

ЗАХИАЛГЫН ЯВЦ:
1️⃣ Хэрэглэгч цаг захиалахыг хүсвэл → үйлчилгээний төрөл асуух
2️⃣ Боломжит өдрүүдийг харуулах (get_next_available_days)
3️⃣ Өдөр сонгосон бол → тухайн өдрийн цагийг харуулах (get_available_slots)
4️⃣ Цаг сонгосон бол → нэр, утас асуух (аль хэдийн мэдэж байвал баталгаажуулах)
5️⃣ Бүгдийг баталгаажуулсны дараа → book_appointment дуудах (facebook_psid={facebook_psid})
6️⃣ Амжилтын мессеж илгээх: огноо, цаг, үйлчилгээ, хаяг зэргийг оруулах"""


def _build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}\n[facebook_psid: {facebook_psid}]"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])


def _build_agent() -> AgentExecutor:
    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=config.ANTHROPIC_API_KEY,
        temperature=0.3,
        max_tokens=2048,
    )
    prompt = _build_prompt()
    agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt)
    return AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10,
    )


# Singleton agent executor
_agent_executor: AgentExecutor | None = None


def get_agent() -> AgentExecutor:
    global _agent_executor
    if _agent_executor is None:
        _agent_executor = _build_agent()
    return _agent_executor


# ─── Main chat function ────────────────────────────────────────────────────────

def chat(psid: str, user_message: str, user_name: str = "") -> str:
    """
    Хэрэглэгчийн мессежийг боловсруулж хариу буцаана.

    psid: Facebook Page-Scoped User ID
    user_message: хэрэглэгчийн мессеж
    user_name: Facebook-аас авсан нэр (байж болно)
    """
    # 1. Хэрэглэгчийн профайл авах / үүсгэх
    user = get_or_create_user(psid, name=user_name)

    # 2. Шинэ lead бол Telegram мэдэгдэл
    if user["is_new_lead"]:
        notify_new_lead(
            facebook_psid=psid,
            user_name=user_name or user["name"] or "Тодорхойгүй",
            first_message=user_message,
        )
        mark_lead_notified(psid)

    # 3. Харилцааны түүх авах
    history = get_conversation_history(psid, limit=10)
    chat_history = []
    for msg in history:
        if msg["role"] == "human":
            chat_history.append(HumanMessage(content=msg["content"]))
        else:
            chat_history.append(AIMessage(content=msg["content"]))

    # 4. Memory context
    memory_ctx = build_memory_context(psid)
    memory_section = f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n📝 ХЭРЭГЛЭГЧИЙН МЭДЭЭЛЭЛ:\n{memory_ctx}\n" if memory_ctx else ""

    # 5. Agent-ийг ажиллуулах
    try:
        agent = get_agent()
        today = datetime.now(UB_TZ).strftime("%Y-%m-%d (%A)")
        result = agent.invoke({
            "input": user_message,
            "chat_history": chat_history,
            "clinic_name": config.CLINIC_NAME,
            "clinic_address": config.CLINIC_ADDRESS,
            "clinic_phone": config.CLINIC_PHONE,
            "working_hours_start": config.CLINIC_WORKING_HOURS_START,
            "working_hours_end": config.CLINIC_WORKING_HOURS_END,
            "today": today,
            "memory_context": memory_section,
            "facebook_psid": psid,
        })
        response = result.get("output") or "Уучлаарай, алдаа гарлаа. Дахин оролдоно уу."
        if not isinstance(response, str):
            response = str(response)
        logger.info(f"Agent output type={type(result.get('output'))}, value={str(response)[:100]}")
    except Exception as e:
        logger.error(f"Agent алдаа (psid={psid}): {e}")
        response = f"Уучлаарай, техникийн алдаа гарлаа. {config.CLINIC_PHONE} дугаарт залгана уу."

    # 6. Мессежийг хадгалах
    save_message(psid, "human", user_message)
    save_message(psid, "assistant", response)

    # 7. Нэр/утас мэдэхгүй байгаа бол хэрэглэгчийн түүхнээс олох (хялбар шалгалт)
    _try_extract_and_save_profile(psid, user_message, user)

    return response


def _try_extract_and_save_profile(psid: str, message: str, current_user: dict) -> None:
    """Хэрэглэгчийн мессежнээс утас / нэр олж хадгалах."""
    import re
    updates = {}
    # Утас: 8 оронтой тоо
    if not current_user.get("phone"):
        phone_match = re.search(r"\b[89]\d{7}\b|\b\d{4}[-\s]\d{4}\b", message)
        if phone_match:
            updates["phone"] = phone_match.group().replace(" ", "").replace("-", "")
    if updates:
        update_user_profile(psid, **updates)
