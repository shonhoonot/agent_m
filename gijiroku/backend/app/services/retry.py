"""指数バックオフ付きリトライヘルパー（Whisper / Claude API 障害対応）。"""
import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    retries: int = 3,
    base_delay: float = 2.0,
    retryable: tuple[type[Exception], ...] = (Exception,),
    label: str = "operation",
) -> T:
    """fn を最大 retries 回、指数バックオフ（2s, 4s, 8s + ジッター）で再試行する。"""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return await fn()
        except retryable as exc:  # noqa: PERF203
            last_exc = exc
            if attempt == retries - 1:
                break
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            logger.warning(
                "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                label, attempt + 1, retries, exc, delay,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc
