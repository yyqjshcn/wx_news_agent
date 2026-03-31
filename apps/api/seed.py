"""
Seed script to populate initial data for testing.
Run with: python apps/api/seed.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_session
from app.models.workflow import Workflow, WorkflowType
from app.models.keyword import Keyword
from app.models.source_account import SourceAccount
import uuid


async def seed():
    async with async_session() as db:
        workflows = [
            {
                "workflow_name": "Daily Ingest",
                "workflow_type": WorkflowType.DAILY_INGEST,
                "cron_expression": "0 8 * * *",
                "timezone": "Asia/Shanghai",
                "enabled": True,
                "config_json": {"batch_size": 50},
            },
            {
                "workflow_name": "Classify Pending Articles",
                "workflow_type": WorkflowType.CLASSIFY_PENDING,
                "cron_expression": "*/30 * * * *",
                "timezone": "Asia/Shanghai",
                "enabled": True,
                "config_json": {},
            },
            {
                "workflow_name": "Generate Daily Digest",
                "workflow_type": WorkflowType.GENERATE_DIGEST,
                "cron_expression": "0 20 * * *",
                "timezone": "Asia/Shanghai",
                "enabled": True,
                "config_json": {},
            },
            {
                "workflow_name": "Login Health Check",
                "workflow_type": WorkflowType.LOGIN_HEALTH_CHECK,
                "cron_expression": "0 */2 * * *",
                "timezone": "Asia/Shanghai",
                "enabled": True,
                "config_json": {},
            },
        ]

        for w in workflows:
            existing = await db.execute(
                Workflow.__table__.select().where(Workflow.workflow_name == w["workflow_name"])
            )
            if not existing.scalar_one_or_none():
                workflow = Workflow(id=str(uuid.uuid4()), **w)
                db.add(workflow)

        keywords = [
            ("具身智能", "industry", 5),
            ("Embodied AI", "industry", 5),
            ("机器人", "industry", 4),
            ("人形机器人", "industry", 5),
            ("VLA", "industry", 4),
            ("Vision-Language-Action", "industry", 4),
            ("世界模型", "industry", 4),
            ("Figure", "company", 3),
            ("Tesla", "company", 3),
            ("Boston Dynamics", "company", 3),
            ("宇树科技", "company", 3),
            ("智元机器人", "company", 3),
            ("融资", "event", 3),
            ("发布", "event", 3),
            ("合作", "event", 2),
            ("量产", "event", 3),
            ("展会", "event", 2),
        ]

        for kw, kw_type, weight in keywords:
            existing = await db.execute(
                Keyword.__table__.select().where(Keyword.keyword == kw)
            )
            if not existing.scalar_one_or_none():
                keyword = Keyword(
                    id=str(uuid.uuid4()),
                    keyword=kw,
                    keyword_type=kw_type,
                    weight=weight,
                )
                db.add(keyword)

        accounts = [
            ("机器之心", "AI Research", "机器之心公众号"),
            ("量子位", "AI News", "量子位公众号"),
            ("新智元", "AI News", "新智元公众号"),
            ("36氪", "Tech News", "36氪公众号"),
        ]

        for name, category, notes in accounts:
            existing = await db.execute(
                SourceAccount.__table__.select().where(SourceAccount.account_name == name)
            )
            if not existing.scalar_one_or_none():
                account = SourceAccount(
                    id=str(uuid.uuid4()),
                    account_name=name,
                    category=category,
                    notes=notes,
                    priority=5,
                )
                db.add(account)

        await db.commit()
        print("Seed data created successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
