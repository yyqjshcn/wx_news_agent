from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import providers, source_accounts, keywords, workflows, content, wechat, system, feishu_webhooks
from app.db.database import engine
from app.db.base import Base


async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Embodied News Agent API",
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


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
