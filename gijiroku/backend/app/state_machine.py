"""会議ステータスの状態遷移マシン。

draft → uploaded → transcribing → generating → ready → published
(transcript 直接貼り付け時は draft → generating)
失敗時は published 以外のどの状態からも failed へ。failed からは再試行可能。
"""

DRAFT = "draft"
UPLOADED = "uploaded"
TRANSCRIBING = "transcribing"
GENERATING = "generating"
READY = "ready"
PUBLISHED = "published"
FAILED = "failed"

ALL_STATUSES = {DRAFT, UPLOADED, TRANSCRIBING, GENERATING, READY, PUBLISHED, FAILED}

_TRANSITIONS: dict[str, set[str]] = {
    DRAFT: {UPLOADED, GENERATING, FAILED},
    UPLOADED: {TRANSCRIBING, FAILED},
    TRANSCRIBING: {GENERATING, FAILED},
    GENERATING: {READY, FAILED},
    READY: {PUBLISHED, GENERATING, FAILED},  # ready → generating で再生成を許可
    PUBLISHED: set(),  # 公開後はロック
    FAILED: {UPLOADED, GENERATING},  # 再試行
}


class InvalidTransition(Exception):
    def __init__(self, current: str, new: str):
        self.current = current
        self.new = new
        super().__init__(f"invalid status transition: {current} -> {new}")


def can_transition(current: str, new: str) -> bool:
    return new in _TRANSITIONS.get(current, set())


def transition(current: str, new: str) -> str:
    """遷移を検証し、新ステータスを返す。不正な遷移は InvalidTransition。"""
    if not can_transition(current, new):
        raise InvalidTransition(current, new)
    return new


# 処理中（ポーリング継続が必要）の状態
PROCESSING_STATUSES = {UPLOADED, TRANSCRIBING, GENERATING}
