"""Slack Incoming Webhook への議事録公開通知。"""
import logging

import httpx

from ..config import get_settings
from ..schemas import MinutesContent
from .retry import retry_async

logger = logging.getLogger(__name__)


def build_slack_message(
    *, title: str, date: str, content: MinutesContent, meeting_url: str
) -> dict:
    decisions = content.kettei_jikou[:3]
    decisions_text = "\n".join(f"• {d}" for d in decisions) if decisions else "（なし）"
    text = (
        ":memo: 議事録が公開されました\n"
        f"*会議名:* {title}\n"
        f"*日時:* {date or '不明'}\n"
        f"*決定事項:*\n{decisions_text}\n"
        f"*アクションアイテム:* {len(content.action_items)}件\n"
        f"{meeting_url}"
    )
    return {"text": text}


async def notify_published(*, title: str, date: str, content: MinutesContent, meeting_id: str) -> bool:
    settings = get_settings()
    if not settings.slack_webhook_url:
        logger.warning("SLACK_WEBHOOK_URL 未設定のため Slack 通知をスキップ")
        return False
    payload = build_slack_message(
        title=title,
        date=date,
        content=content,
        meeting_url=f"{settings.app_base_url}/meetings/{meeting_id}",
    )

    async def _post() -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.slack_webhook_url, json=payload)
            resp.raise_for_status()

    try:
        await retry_async(_post, label="slack notify")
        return True
    except Exception:
        logger.exception("Slack 通知に失敗しました（meeting %s）", meeting_id)
        return False
