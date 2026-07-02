"""議事録 JSON のパース・検証テスト。"""
import json

import pytest

from app.schemas import MinutesContent
from app.services.minutes import MinutesGenerationError, parse_minutes_json


def test_valid_minutes_json_parses(valid_minutes_dict):
    content = parse_minutes_json(json.dumps(valid_minutes_dict, ensure_ascii=False))
    assert content.kaigi_gaiyou.kaigi_mei == "週次定例会議"
    assert content.gidai == ["売上報告", "新製品ローンチ"]
    assert content.action_items[0].tantousha == "佐藤"


def test_invalid_json_raises():
    with pytest.raises(MinutesGenerationError):
        parse_minutes_json("これはJSONではありません {")


def test_missing_required_section_raises(valid_minutes_dict):
    del valid_minutes_dict["kettei_jikou"]
    with pytest.raises(MinutesGenerationError):
        parse_minutes_json(json.dumps(valid_minutes_dict, ensure_ascii=False))


def test_markdown_export_contains_all_sections(valid_minutes_dict):
    from app.services.export import render_markdown

    md = render_markdown(MinutesContent.model_validate(valid_minutes_dict))
    for section in ["# 議事録", "## 会議概要", "## 議題", "## 議論内容",
                    "## 決定事項", "## アクションアイテム", "## 次回会議",
                    "## 保留・継続検討事項"]:
        assert section in md
    assert "| 1 | プレスリリース草稿作成 | 佐藤 | 6月20日 |" in md
