"""アクションアイテム抽出のエッジケース。"""
from app.schemas import ActionItemSchema, MinutesContent


def test_empty_assignee_normalized_to_mitei():
    item = ActionItemSchema(no=1, naiyou="資料作成", tantousha="", kigen="")
    assert item.tantousha == "未定"
    assert item.kigen == "未定"


def test_whitespace_assignee_normalized_to_mitei():
    item = ActionItemSchema(no=2, naiyou="レビュー依頼", tantousha="   ", kigen="\t")
    assert item.tantousha == "未定"
    assert item.kigen == "未定"


def test_empty_action_items_list_is_valid(valid_minutes_dict):
    valid_minutes_dict["action_items"] = []
    content = MinutesContent.model_validate(valid_minutes_dict)
    assert content.action_items == []


def test_slack_message_top3_decisions(valid_minutes_dict):
    from app.services.slack import build_slack_message

    valid_minutes_dict["kettei_jikou"] = ["決定1", "決定2", "決定3", "決定4"]
    content = MinutesContent.model_validate(valid_minutes_dict)
    msg = build_slack_message(
        title="定例", date="2026年06月10日", content=content,
        meeting_url="http://localhost:3000/meetings/x",
    )
    assert "決定3" in msg["text"]
    assert "決定4" not in msg["text"]  # 上位3件のみ
    assert "アクションアイテム:* 1件" in msg["text"]
