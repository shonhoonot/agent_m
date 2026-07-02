"""非同期処理パイプライン。

MVP では FastAPI BackgroundTasks から呼ばれるが、エントリポイントが
`run_pipeline(meeting_id, ...)` の単一関数なので、将来 Celery / RQ 等の
キューワーカーへそのまま差し替え可能。
"""
import logging

from sqlalchemy import delete, select

from ..database import SessionLocal
from ..models import ActionItem, Meeting, Minutes, Transcript
from ..schemas import MinutesContent
from .. import state_machine as sm
from .minutes import MinutesGenerationError, cleanup_transcript, generate_minutes
from .transcription import TranscriptionError, transcribe

logger = logging.getLogger(__name__)


async def _set_status(meeting_id: str, new_status: str, error_detail: str | None = None) -> None:
    async with SessionLocal() as db:
        meeting = await db.get(Meeting, meeting_id)
        if meeting is None:
            return
        meeting.status = sm.transition(meeting.status, new_status)
        meeting.error_detail = error_detail
        await db.commit()


async def sync_action_items(db, meeting_id: str, content: MinutesContent) -> None:
    """minutes JSON の action_items を action_items テーブルへ反映する。"""
    await db.execute(delete(ActionItem).where(ActionItem.meeting_id == meeting_id))
    for item in content.action_items:
        db.add(
            ActionItem(
                meeting_id=meeting_id,
                no=item.no,
                content=item.naiyou,
                assignee=item.tantousha,
                due_date=item.kigen,
            )
        )


async def save_minutes(db, meeting_id: str, content: MinutesContent, *, edited_by_user: bool) -> Minutes:
    result = await db.execute(
        select(Minutes)
        .where(Minutes.meeting_id == meeting_id)
        .order_by(Minutes.version.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    record = Minutes(
        meeting_id=meeting_id,
        content=content.model_dump(),
        version=(latest.version + 1) if latest else 1,
        edited_by_user=edited_by_user,
    )
    db.add(record)
    await sync_action_items(db, meeting_id, content)
    return record


async def run_pipeline(meeting_id: str, *, skip_transcription: bool = False) -> None:
    """音声 → 文字起こし → クリーンアップ → 議事録生成 → ready。"""
    try:
        async with SessionLocal() as db:
            meeting = await db.get(Meeting, meeting_id)
            if meeting is None:
                logger.error("meeting %s not found, aborting pipeline", meeting_id)
                return
            attendees = list(meeting.attendees or [])
            absentees = list(meeting.absentees or [])
            title = meeting.title
            meeting_date = meeting.meeting_date
            location = meeting.location
            audio_path = meeting.audio_path

        # --- 文字起こし ---
        if not skip_transcription:
            await _set_status(meeting_id, sm.TRANSCRIBING)
            result = await transcribe(audio_path)
            async with SessionLocal() as db:
                existing = (
                    await db.execute(select(Transcript).where(Transcript.meeting_id == meeting_id))
                ).scalar_one_or_none()
                if existing:
                    existing.raw_text = result.text
                    existing.duration_sec = result.duration_sec
                else:
                    db.add(
                        Transcript(
                            meeting_id=meeting_id,
                            raw_text=result.text,
                            duration_sec=result.duration_sec,
                        )
                    )
                await db.commit()

        # --- 議事録生成（2パス） ---
        await _set_status(meeting_id, sm.GENERATING)
        async with SessionLocal() as db:
            transcript = (
                await db.execute(select(Transcript).where(Transcript.meeting_id == meeting_id))
            ).scalar_one()
            raw_text = transcript.raw_text

        cleaned = await cleanup_transcript(raw_text, attendees)
        content = await generate_minutes(
            cleaned,
            title=title,
            meeting_date=meeting_date,
            location=location,
            attendees=attendees,
            absentees=absentees,
        )

        async with SessionLocal() as db:
            transcript = (
                await db.execute(select(Transcript).where(Transcript.meeting_id == meeting_id))
            ).scalar_one()
            transcript.cleaned_text = cleaned
            await save_minutes(db, meeting_id, content, edited_by_user=False)
            await db.commit()

        await _set_status(meeting_id, sm.READY)
        logger.info("pipeline completed for meeting %s", meeting_id)

    except (TranscriptionError, MinutesGenerationError) as exc:
        logger.exception("pipeline failed for meeting %s", meeting_id)
        await _set_status(meeting_id, sm.FAILED, str(exc))
    except Exception:
        logger.exception("unexpected pipeline error for meeting %s", meeting_id)
        await _set_status(
            meeting_id, sm.FAILED, "処理中に予期しないエラーが発生しました。再度お試しください。"
        )
