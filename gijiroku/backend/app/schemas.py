"""Pydantic スキーマ。MinutesContent は Claude の構造化出力スキーマと 1:1 対応。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------- 議事録 JSON（仕様セクション4） ----------

class KaigiGaiyou(BaseModel):
    kaigi_mei: str = ""
    nichiji: str = ""
    basho: str = ""
    shussekisha: list[str] = Field(default_factory=list)
    kessekisha: list[str] = Field(default_factory=list)


class Youten(BaseModel):
    hatsugensha: str = ""
    naiyou: str = ""


class GironNaiyou(BaseModel):
    gidai: str = ""
    youten: list[Youten] = Field(default_factory=list)


class ActionItemSchema(BaseModel):
    no: int = 1
    naiyou: str = ""
    tantousha: str = "未定"
    kigen: str = "未定"

    @field_validator("tantousha", "kigen", mode="after")
    @classmethod
    def default_mitei(cls, v: str) -> str:
        # 担当者・期限が空欄なら「未定」に正規化（仕様: 期限が明言されない場合は未定）
        return v.strip() or "未定"


class JikaiKaigi(BaseModel):
    nichiji: str = ""
    gidai_yotei: list[str] = Field(default_factory=list)


class MinutesContent(BaseModel):
    kaigi_gaiyou: KaigiGaiyou
    gidai: list[str]
    giron_naiyou: list[GironNaiyou]
    kettei_jikou: list[str]
    action_items: list[ActionItemSchema]
    jikai_kaigi: JikaiKaigi
    horyuu_jikou: list[str]


# Claude 構造化出力用 JSON スキーマ（output_config.format に渡す）
MINUTES_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "kaigi_gaiyou": {
            "type": "object",
            "properties": {
                "kaigi_mei": {"type": "string"},
                "nichiji": {"type": "string"},
                "basho": {"type": "string"},
                "shussekisha": {"type": "array", "items": {"type": "string"}},
                "kessekisha": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["kaigi_mei", "nichiji", "basho", "shussekisha", "kessekisha"],
            "additionalProperties": False,
        },
        "gidai": {"type": "array", "items": {"type": "string"}},
        "giron_naiyou": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gidai": {"type": "string"},
                    "youten": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "hatsugensha": {"type": "string"},
                                "naiyou": {"type": "string"},
                            },
                            "required": ["hatsugensha", "naiyou"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["gidai", "youten"],
                "additionalProperties": False,
            },
        },
        "kettei_jikou": {"type": "array", "items": {"type": "string"}},
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "no": {"type": "integer"},
                    "naiyou": {"type": "string"},
                    "tantousha": {"type": "string"},
                    "kigen": {"type": "string"},
                },
                "required": ["no", "naiyou", "tantousha", "kigen"],
                "additionalProperties": False,
            },
        },
        "jikai_kaigi": {
            "type": "object",
            "properties": {
                "nichiji": {"type": "string"},
                "gidai_yotei": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["nichiji", "gidai_yotei"],
            "additionalProperties": False,
        },
        "horyuu_jikou": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "kaigi_gaiyou", "gidai", "giron_naiyou", "kettei_jikou",
        "action_items", "jikai_kaigi", "horyuu_jikou",
    ],
    "additionalProperties": False,
}


# ---------- API リクエスト / レスポンス ----------

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeetingCreate(BaseModel):
    title: str
    meeting_date: str | None = None
    location: str | None = None
    attendees: list[str] = Field(default_factory=list)
    absentees: list[str] = Field(default_factory=list)


class TranscriptPaste(BaseModel):
    text: str


class MinutesUpdate(BaseModel):
    content: MinutesContent


class ActionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    no: int
    content: str
    assignee: str
    due_date: str
    done: bool


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    meeting_date: str | None
    location: str | None
    attendees: list[str] | None
    absentees: list[str] | None
    status: str
    error_detail: str | None
    created_at: datetime
    published_at: datetime | None


class MeetingDetail(MeetingOut):
    transcript_raw: str | None = None
    transcript_cleaned: str | None = None
    minutes: MinutesContent | None = None
    minutes_version: int | None = None
    action_items: list[ActionItemOut] = Field(default_factory=list)


class MeetingList(BaseModel):
    items: list[MeetingOut]
    total: int
    page: int
    page_size: int
