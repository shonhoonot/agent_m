"""OpenAI Whisper API による文字起こし。25MB 超の音声は分割して送信する。"""
import logging
import os
import tempfile
from dataclasses import dataclass

from openai import AsyncOpenAI

from ..config import get_settings
from .retry import retry_async

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".mp3", ".m4a", ".wav"}


class TranscriptionError(Exception):
    """文字起こし失敗（UI 向け日本語メッセージを保持）。"""


@dataclass
class TranscriptionResult:
    text: str
    duration_sec: float
    language: str = "ja"


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=get_settings().openai_api_key)


def split_audio(path: str, limit_bytes: int) -> list[str]:
    """音声ファイルを Whisper API の上限以下のチャンクに分割する。

    ファイルサイズと再生時間がほぼ比例すると仮定し、サイズ比から
    チャンク長（ミリ秒）を決めて mp3 で書き出す。分割不要ならそのまま返す。
    """
    size = os.path.getsize(path)
    if size <= limit_bytes:
        return [path]

    from pydub import AudioSegment  # 遅延 import（ffmpeg 依存）

    audio = AudioSegment.from_file(path)
    # 安全マージン 10% を取ってチャンク数を決定
    n_chunks = int(size / (limit_bytes * 0.9)) + 1
    chunk_ms = len(audio) // n_chunks + 1
    tmpdir = tempfile.mkdtemp(prefix="gijiroku_chunks_")
    paths: list[str] = []
    for i in range(0, len(audio), chunk_ms):
        chunk_path = os.path.join(tmpdir, f"chunk_{i // chunk_ms:03d}.mp3")
        audio[i : i + chunk_ms].export(chunk_path, format="mp3", bitrate="64k")
        paths.append(chunk_path)
    logger.info("split audio into %d chunks (%d bytes total)", len(paths), size)
    return paths


async def transcribe(path: str) -> TranscriptionResult:
    """音声ファイル全体を文字起こしする（必要に応じて分割・連結）。"""
    settings = get_settings()
    try:
        chunk_paths = split_audio(path, settings.whisper_limit_bytes)
    except Exception as exc:
        raise TranscriptionError(
            "音声ファイルの分割に失敗しました。ファイル形式をご確認ください。"
        ) from exc

    client = _client()
    texts: list[str] = []
    total_duration = 0.0
    for chunk_path in chunk_paths:
        async def _call(p: str = chunk_path):
            with open(p, "rb") as f:
                return await client.audio.transcriptions.create(
                    model=settings.whisper_model,
                    file=f,
                    language="ja",
                    response_format="verbose_json",
                )

        try:
            result = await retry_async(_call, label="whisper transcription")
        except Exception as exc:
            raise TranscriptionError(
                "文字起こしに失敗しました。しばらくしてから再度お試しください。"
            ) from exc
        texts.append(result.text)
        total_duration += float(getattr(result, "duration", 0.0) or 0.0)

    return TranscriptionResult(text="\n".join(texts), duration_sec=total_duration)
