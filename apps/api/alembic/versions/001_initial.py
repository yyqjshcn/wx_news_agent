"""empty message

Revision ID: initial
Revises:
Create Date: 2026-03-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('llm_providers',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('provider_type', sa.String(), nullable=False, server_default='openai_compatible'),
        sa.Column('base_url', sa.String(), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=False),
        sa.Column('default_model', sa.String(), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default='true'),
        sa.Column('is_default_for_relevance', sa.Boolean(), server_default='false'),
        sa.Column('is_default_for_extraction', sa.Boolean(), server_default='false'),
        sa.Column('is_default_for_digest', sa.Boolean(), server_default='false'),
        sa.Column('request_timeout', sa.Integer(), server_default='30'),
        sa.Column('max_retries', sa.Integer(), server_default='3'),
        sa.Column('extra_headers_json', sa.JSON(), server_default='{}'),
        sa.Column('extra_query_json', sa.JSON(), server_default='{}'),
        sa.Column('last_test_status', sa.String(), nullable=True),
        sa.Column('last_test_message', sa.Text(), nullable=True),
        sa.Column('last_test_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_table('source_accounts',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('account_name', sa.String(), nullable=False),
        sa.Column('account_alias', sa.String(), nullable=True),
        sa.Column('fakeid', sa.String(), nullable=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('priority', sa.Integer(), server_default='5'),
        sa.Column('enabled', sa.Boolean(), server_default='true'),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_table('keywords',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('keyword', sa.String(), nullable=False),
        sa.Column('keyword_type', sa.String(), nullable=False, server_default='industry'),
        sa.Column('weight', sa.Integer(), server_default='1'),
        sa.Column('enabled', sa.Boolean(), server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_table('workflows',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('workflow_name', sa.String(), nullable=False),
        sa.Column('workflow_type', sa.String(), nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default='true'),
        sa.Column('cron_expression', sa.String(), nullable=False),
        sa.Column('timezone', sa.String(), server_default='Asia/Shanghai'),
        sa.Column('config_json', sa.JSON(), server_default='{}'),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_table('workflow_runs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('trigger_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), server_default='pending'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('summary_json', sa.JSON(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )
    op.create_table('raw_articles',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('article_url', sa.String(), nullable=False, unique=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('account_name', sa.String(), nullable=False),
        sa.Column('fakeid', sa.String(), nullable=True),
        sa.Column('publish_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('author', sa.String(), nullable=True),
        sa.Column('plain_content', sa.Text(), nullable=True),
        sa.Column('html_content', sa.Text(), nullable=True),
        sa.Column('content_hash', sa.String(), nullable=True),
        sa.Column('title_normalized', sa.String(), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True)),
        sa.Column('status', sa.String(), server_default='new'),
        sa.Column('is_relevant', sa.Boolean(), nullable=True),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('primary_event_type', sa.String(), nullable=True),
        sa.Column('tags_json', sa.JSON(), server_default='[]'),
        sa.Column('companies_json', sa.JSON(), server_default='[]'),
        sa.Column('summary_short', sa.Text(), nullable=True),
        sa.Column('summary_long', sa.Text(), nullable=True),
        sa.Column('llm_provider_id', sa.String(), nullable=True),
        sa.Column('llm_model', sa.String(), nullable=True),
        sa.Column('raw_llm_output_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_table('curated_events',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('article_id', sa.String(), nullable=False),
        sa.Column('company_name', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=True),
        sa.Column('importance', sa.Integer(), server_default='3'),
        sa.Column('one_line_summary', sa.Text(), nullable=True),
        sa.Column('analyst_note', sa.Text(), nullable=True),
        sa.Column('included_in_digest', sa.Boolean(), server_default='false'),
        sa.Column('event_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_table('daily_digests',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('digest_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('content_markdown', sa.Text(), nullable=True),
        sa.Column('content_html', sa.Text(), nullable=True),
        sa.Column('item_count', sa.Integer(), server_default='0'),
        sa.Column('status', sa.String(), server_default='draft'),
        sa.Column('llm_provider_id', sa.String(), nullable=True),
        sa.Column('llm_model', sa.String(), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_table('login_sessions',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('provider_name', sa.String(), nullable=False, server_default='wechat'),
        sa.Column('status', sa.String(), nullable=False, server_default='unknown'),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_table('system_logs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('level', sa.String(), nullable=False, server_default='INFO'),
        sa.Column('module', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('payload_json', sa.JSON(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table('system_logs')
    op.drop_table('login_sessions')
    op.drop_table('daily_digests')
    op.drop_table('curated_events')
    op.drop_table('raw_articles')
    op.drop_table('workflow_runs')
    op.drop_table('workflows')
    op.drop_table('keywords')
    op.drop_table('source_accounts')
    op.drop_table('llm_providers')
