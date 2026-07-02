"""ステータス状態遷移マシンのテスト。"""
import pytest

from app import state_machine as sm


def test_happy_path_transitions():
    status = sm.DRAFT
    for next_status in [sm.UPLOADED, sm.TRANSCRIBING, sm.GENERATING, sm.READY, sm.PUBLISHED]:
        status = sm.transition(status, next_status)
    assert status == sm.PUBLISHED


def test_paste_transcript_skips_whisper():
    assert sm.can_transition(sm.DRAFT, sm.GENERATING)


def test_published_is_locked():
    for target in sm.ALL_STATUSES - {sm.PUBLISHED}:
        assert not sm.can_transition(sm.PUBLISHED, target)


def test_invalid_transition_raises():
    with pytest.raises(sm.InvalidTransition):
        sm.transition(sm.DRAFT, sm.READY)


def test_failed_allows_retry():
    assert sm.can_transition(sm.FAILED, sm.UPLOADED)
    assert sm.can_transition(sm.FAILED, sm.GENERATING)
    assert sm.can_transition(sm.GENERATING, sm.FAILED)
