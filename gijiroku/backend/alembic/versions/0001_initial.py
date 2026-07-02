"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-10

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "meetings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("meeting_date", sa.String(64)),
        sa.Column("location", sa.String(255)),
        sa.Column("attendees", sa.JSON()),
        sa.Column("absentees", sa.JSON()),
        sa.Column("status", sa.String(32), nullable=False, index=True),
        sa.Column("error_detail", sa.Text()),
        sa.Column("audio_path", sa.String(512)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "transcripts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id"), nullable=False, unique=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("cleaned_text", sa.Text()),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("duration_sec", sa.Float()),
    )
    op.create_table(
        "minutes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id"), nullable=False, index=True),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("edited_by_user", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "action_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id"), nullable=False, index=True),
        sa.Column("no", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("assignee", sa.String(255), nullable=False),
        sa.Column("due_date", sa.String(64), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("action_items")
    op.drop_table("minutes")
    op.drop_table("transcripts")
    op.drop_table("meetings")
    op.drop_table("users")
