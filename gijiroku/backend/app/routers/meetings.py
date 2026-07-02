import os
import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import state_machine as sm
from ..auth import get_current_user
from ..config import get_settings
from ..database import get_db
from ..models import ActionItem, Meeting, Minutes, Transcript, User
from ..schemas import (
    ActionItemOut,
    MeetingCreate,
    MeetingDetail,
    MeetingList,
    MeetingOut,
    MinutesContent,
    MinutesUpdate,
    TranscriptPaste,
)
from ..services import pipeline
from ..services.export import render_docx, render_markdown
from ..services.slack import notify_published
from ..services.transcription import ALLOWED_EXTENSIONS

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


async def _get_meeting(meeting_id: str, user: User, db: AsyncSession) -> Meeting:
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None or meeting.user_id != user.id:
        raise HTTPException(status_code=404, detail="会議が見つかりません。")
    return meeting


async def _latest_minutes(db: AsyncSession, meeting_id: str) -> Minutes | None:
    return (
        await db.execute(
            select(Minutes)
            .where(Minutes.meeting_id == meeting_id)
            .order_by(Minutes.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@router.post("", response_model=MeetingOut, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    body: MeetingCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Meeting:
    meeting = Meeting(
        user_id=user.id,
        title=body.title,
        meeting_date=body.meeting_date,
        location=body.location,
        attendees=body.attendees,
        absentees=body.absentees,
        status=sm.DRAFT,
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)
    return meeting


@router.get("", response_model=MeetingList)
async def list_meetings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, description="会議名・日時の検索キーワード"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingList:
    base = select(Meeting).where(Meeting.user_id == user.id)
    if q:
        base = base.where(
            or_(Meeting.title.ilike(f"%{q}%"), Meeting.meeting_date.ilike(f"%{q}%"))
        )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base.order_by(Meeting.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return MeetingList(
        items=[MeetingOut.model_validate(m) for m in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{meeting_id}", response_model=MeetingDetail)
async def get_meeting(
    meeting_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingDetail:
    meeting = (
        await db.execute(
            select(Meeting)
            .where(Meeting.id == meeting_id, Meeting.user_id == user.id)
            .options(selectinload(Meeting.transcript), selectinload(Meeting.action_items))
        )
    ).scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=404, detail="会議が見つかりません。")
    latest = await _latest_minutes(db, meeting_id)
    detail = MeetingDetail.model_validate(meeting)
    if meeting.transcript:
        detail.transcript_raw = meeting.transcript.raw_text
        detail.transcript_cleaned = meeting.transcript.cleaned_text
    if latest:
        detail.minutes = MinutesContent.model_validate(latest.content)
        detail.minutes_version = latest.version
    detail.action_items = [ActionItemOut.model_validate(a) for a in meeting.action_items]
    return detail


@router.post("/{meeting_id}/audio", response_model=MeetingOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_audio(
    meeting_id: str,
    file: UploadFile,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Meeting:
    settings = get_settings()
    meeting = await _get_meeting(meeting_id, user, db)
    if not sm.can_transition(meeting.status, sm.UPLOADED):
        raise HTTPException(status_code=409, detail="現在のステータスでは音声をアップロードできません。")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="対応形式は .mp3 / .m4a / .wav のみです。"
        )

    os.makedirs(settings.upload_dir, exist_ok=True)
    dest = os.path.join(settings.upload_dir, f"{meeting_id}_{uuid.uuid4().hex}{ext}")
    size = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_upload_bytes:
                out.close()
                os.unlink(dest)
                raise HTTPException(
                    status_code=413, detail="ファイルサイズの上限は 200MB です。"
                )
            out.write(chunk)

    meeting.status = sm.transition(meeting.status, sm.UPLOADED)
    meeting.audio_path = dest
    meeting.error_detail = None
    await db.commit()
    await db.refresh(meeting)
    background.add_task(pipeline.run_pipeline, meeting_id)
    return meeting


@router.post("/{meeting_id}/transcript", response_model=MeetingOut, status_code=status.HTTP_202_ACCEPTED)
async def paste_transcript(
    meeting_id: str,
    body: TranscriptPaste,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Meeting:
    meeting = await _get_meeting(meeting_id, user, db)
    if not sm.can_transition(meeting.status, sm.GENERATING):
        raise HTTPException(status_code=409, detail="現在のステータスでは文字起こしを登録できません。")
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="文字起こしテキストを入力してください。")

    existing = (
        await db.execute(select(Transcript).where(Transcript.meeting_id == meeting_id))
    ).scalar_one_or_none()
    if existing:
        existing.raw_text = body.text
        existing.cleaned_text = None
    else:
        db.add(Transcript(meeting_id=meeting_id, raw_text=body.text))
    meeting.status = sm.transition(meeting.status, sm.GENERATING)
    meeting.error_detail = None
    await db.commit()
    await db.refresh(meeting)
    background.add_task(pipeline.run_pipeline, meeting_id, skip_transcription=True)
    return meeting


@router.patch("/{meeting_id}/minutes", response_model=MeetingDetail)
async def update_minutes(
    meeting_id: str,
    body: MinutesUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeetingDetail:
    meeting = await _get_meeting(meeting_id, user, db)
    if meeting.status == sm.PUBLISHED:
        raise HTTPException(status_code=409, detail="公開済みの議事録は編集できません。")
    if meeting.status != sm.READY:
        raise HTTPException(status_code=409, detail="議事録の生成完了後に編集できます。")
    await pipeline.save_minutes(db, meeting_id, body.content, edited_by_user=True)
    await db.commit()
    return await get_meeting(meeting_id, user, db)


@router.post("/{meeting_id}/publish", response_model=MeetingOut)
async def publish_meeting(
    meeting_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Meeting:
    meeting = await _get_meeting(meeting_id, user, db)
    if not sm.can_transition(meeting.status, sm.PUBLISHED):
        raise HTTPException(status_code=409, detail="議事録が完成していないため公開できません。")
    latest = await _latest_minutes(db, meeting_id)
    if latest is None:
        raise HTTPException(status_code=409, detail="議事録が存在しません。")

    content = MinutesContent.model_validate(latest.content)
    meeting.status = sm.transition(meeting.status, sm.PUBLISHED)
    meeting.published_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(meeting)

    await notify_published(
        title=meeting.title,
        date=meeting.meeting_date or content.kaigi_gaiyou.nichiji,
        content=content,
        meeting_id=meeting.id,
    )
    return meeting


@router.get("/{meeting_id}/export")
async def export_minutes(
    meeting_id: str,
    format: str = Query("md", pattern="^(docx|md)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await _get_meeting(meeting_id, user, db)
    latest = await _latest_minutes(db, meeting_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="議事録が存在しません。")
    content = MinutesContent.model_validate(latest.content)

    if format == "md":
        return Response(
            content=render_markdown(content),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="gijiroku_{meeting_id}.md"'},
        )
    return Response(
        content=render_docx(content),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="gijiroku_{meeting_id}.docx"'},
    )
