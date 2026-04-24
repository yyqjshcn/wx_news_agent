from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import providers, source_accounts, keywords, workflows, content, wechat, system, feishu_webhooks, email_configs, rss_feeds, notification_channels
from app.db.database import engine
from app.db.base import Base
from app.core.scheduler import start_scheduler, stop_scheduler
import logging

logger = logging.getLogger(__name__)


async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    scheduler = None
    try:
        scheduler = await start_scheduler()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    yield
    
    if scheduler:
        await stop_scheduler(scheduler)


app = FastAPI(
    title="OmniNewsFlow API",
    description="Local WeChat intelligence briefing system",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(providers.router)
app.include_router(source_accounts.router)
app.include_router(keywords.router)
app.include_router(workflows.router)
app.include_router(content.router)
app.include_router(wechat.router)
app.include_router(system.router)
app.include_router(feishu_webhooks.router)
app.include_router(email_configs.router)
app.include_router(rss_feeds.router)
app.include_router(notification_channels.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
