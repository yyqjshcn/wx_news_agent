"""add aggregated event tables

Revision ID: 002_aggregated_events
Revises: initial
Create Date: 2026-04-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002_aggregated_events"
down_revision: Union[str, None] = "initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("importance", sa.Integer(), server_default="3"),
        sa.Column("summary_short", sa.Text(), nullable=True),
        sa.Column("summary_long", sa.Text(), nullable=True),
        sa.Column("analyst_note", sa.Text(), nullable=True),
        sa.Column("included_in_digest", sa.Boolean(), server_default="false"),
        sa.Column("created_by_strategy", sa.String(), server_default="auto"),
        sa.Column("event_date_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_date_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "article_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("article_id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), server_default="source"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("article_id", "event_id", name="uq_article_events_article_event"),
    )
    op.create_table(
        "event_entities",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), server_default="company"),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("normalized_name", sa.String(), nullable=True),
        sa.Column("role", sa.String(), server_default="participant"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("event_entities")
    op.drop_table("article_events")
    op.drop_table("events")
