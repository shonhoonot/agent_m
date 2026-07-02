"""Claude による議事録生成（2パス処理）。

Pass 1: 文字起こしのクリーンアップ（誤変換修正・フィラー除去・話者ラベル付け）
Pass 2: 正式な議事録 JSON の生成 — 構造化出力（output_config.format）でスキーマを保証
"""
import json
import logging

import anthropic
from pydantic import ValidationError

from ..config import get_settings
from ..schemas import MINUTES_JSON_SCHEMA, MinutesContent
from .retry import retry_async

logger = logging.getLogger(__name__)


class MinutesGenerationError(Exception):
    """議事録生成失敗（UI 向け日本語メッセージを保持）。"""


# 仕様セクション5の Claude システムプロンプト
MINUTES_SYSTEM_PROMPT = """あなたは日本企業の会議の書記を務めるプロフェッショナルなAIアシスタントです。
会議の文字起こしを読み、正式なビジネス議事録を作成してください。

ルール:
- 敬体（です・ます調）ではなく、議事録の慣例に従い体言止め・簡潔な常体で記述する
- 発言の逐語記録ではなく、要点を整理して記載する
- 決定事項と単なる議論・意見を明確に区別する
- アクションアイテムは「誰が・何を・いつまでに」を必ず特定する。期限が明言されていない場合は「未定」とする
- 文字起こしに誤変換と思われる箇所は文脈から推測して修正する
- 推測で情報を追加しない。不明な項目は「不明」または空欄とする
- 出力は指定されたJSONスキーマのみ。それ以外のテキストを含めない"""

CLEANUP_SYSTEM_PROMPT = """あなたは日本語の会議文字起こしを整形する専門アシスタントです。
以下のルールで文字起こしを読みやすく整形してください。

ルール:
- 明らかな誤変換・誤認識を文脈から推測して修正する
- フィラー（えーと、あのー、まあ、など）を削除する
- 発言の内容自体は変更しない（要約しない）
- 発言ごとに話者ラベルを付ける。出席者名が分かる場合は実名、不明な場合は「話者A」「話者B」のように区別する
- 出力は整形後のテキストのみ。前置きや説明を含めない"""


def _client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)


def parse_minutes_json(text: str) -> MinutesContent:
    """Claude の応答テキストを検証済み MinutesContent に変換する。"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MinutesGenerationError(
            "議事録データの解析に失敗しました。再生成をお試しください。"
        ) from exc
    try:
        return MinutesContent.model_validate(data)
    except ValidationError as exc:
        raise MinutesGenerationError(
            "議事録データの形式が不正です。再生成をお試しください。"
        ) from exc


async def cleanup_transcript(raw_text: str, attendees: list[str] | None = None) -> str:
    """Pass 1: 話者ラベル付きクリーンアップ。"""
    settings = get_settings()
    client = _client()
    attendee_note = (
        f"\n\n出席者リスト（話者ラベルの参考にしてください）: {', '.join(attendees)}"
        if attendees
        else ""
    )

    async def _call() -> str:
        async with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=32000,
            system=CLEANUP_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"次の会議文字起こしを整形してください。{attendee_note}\n\n---\n{raw_text}",
                }
            ],
        ) as stream:
            message = await stream.get_final_message()
        return next((b.text for b in message.content if b.type == "text"), "")

    try:
        return await retry_async(
            _call,
            retryable=(anthropic.APIStatusError, anthropic.APIConnectionError),
            label="claude transcript cleanup",
        )
    except anthropic.APIError as exc:
        raise MinutesGenerationError(
            "文字起こしの整形に失敗しました。しばらくしてから再度お試しください。"
        ) from exc


async def generate_minutes(
    cleaned_text: str,
    *,
    title: str,
    meeting_date: str | None,
    location: str | None,
    attendees: list[str] | None,
    absentees: list[str] | None,
) -> MinutesContent:
    """Pass 2: 構造化出力で議事録 JSON を生成し、検証する。

    構造化出力でスキーマ準拠は API 側で保証されるが、念のため
    Pydantic 検証 + 不正 JSON 時の再試行（3回・指数バックオフ）を行う。
    """
    settings = get_settings()
    client = _client()
    meta_lines = [f"会議名: {title}"]
    if meeting_date:
        meta_lines.append(f"日時: {meeting_date}")
    if location:
        meta_lines.append(f"場所: {location}")
    if attendees:
        meta_lines.append(f"出席者: {', '.join(attendees)}")
    if absentees:
        meta_lines.append(f"欠席者: {', '.join(absentees)}")
    user_content = (
        "次の会議情報と文字起こしから議事録 JSON を作成してください。\n\n"
        "【会議情報】\n" + "\n".join(meta_lines) + "\n\n【文字起こし】\n" + cleaned_text
    )

    async def _call() -> MinutesContent:
        async with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=MINUTES_SYSTEM_PROMPT,
            output_config={
                "format": {"type": "json_schema", "schema": MINUTES_JSON_SCHEMA}
            },
            messages=[{"role": "user", "content": user_content}],
        ) as stream:
            message = await stream.get_final_message()
        text = next((b.text for b in message.content if b.type == "text"), "")
        return parse_minutes_json(text)

    try:
        return await retry_async(
            _call,
            retryable=(
                MinutesGenerationError,
                anthropic.APIStatusError,
                anthropic.APIConnectionError,
            ),
            label="claude minutes generation",
        )
    except MinutesGenerationError:
        raise
    except anthropic.APIError as exc:
        raise MinutesGenerationError(
            "議事録の生成に失敗しました。しばらくしてから再度お試しください。"
        ) from exc
