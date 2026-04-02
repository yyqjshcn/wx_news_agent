# 微信新闻智能体

一个运行在 Windows + WSL 上的本地、自托管微信智能简报系统。

## 架构

- **前端**: Next.js 15 + TypeScript + Tailwind CSS
- **后端 API**: FastAPI (Python 3.11+)
- **任务队列**: Celery + Redis + Celery Beat
- **数据库**: PostgreSQL 16
- **微信适配器**: 侧车服务 (wechat-download-api)
- **LLM 网关**: OpenAI 兼容的提供商抽象层

## 快速开始

### 前置条件

- 安装了 WSL 2 的 Windows（推荐 Ubuntu）
- 使用 WSL 2 后端的 Docker Desktop
- 代码目录需位于 WSL 文件系统内（不要放在 /mnt/c/...）

### 设置

```bash
# 1. 复制环境配置文件
cp .env.example .env

# 2. 生成加密密钥（32 字节十六进制）
python3 -c "import secrets; print(secrets.token_hex(32))"
# 更新 .env 中的 ENCRYPTION_KEY

# 3. 生成密钥
python3 -c "import secrets; print(secrets.token_hex(32))"
# 更新 .env 中的 SECRET_KEY

# 4. 启动所有服务
docker compose up -d

# 5. 访问应用
# 前端: http://localhost:3000
# API: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

## 开发

### 前端 (Next.js)

```bash
cd apps/web
npm install
npm run dev
```

### 后端 (FastAPI)

```bash
cd apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 工作进程 (Celery)

```bash
cd apps/worker
pip install -r requirements.txt
celery -A app.worker worker --loglevel=info
celery -A app.worker beat --loglevel=info
```

## 项目结构

```
embodied-news-agent/
├── apps/
│   ├── web/                  # Next.js 前端
│   ├── api/                  # FastAPI 后端
│   └── worker/               # Celery 工作进程 + 定时任务
├── packages/
│   └── prompt-templates/     # LLM 提示词模板
├── infra/
│   ├── docker/               # Docker 配置
│   └── nginx/                # Nginx 反向代理
├── docs/                     # 文档
├── data/                     # 本地数据文件
├── docker-compose.yml
├── .env.example
└── README.md
```

## 功能特性

- 微信登录状态管理
- 来源账号（公众号）白名单管理
- 关键词管理（支持类型和权重）
- OpenAI 兼容的模型提供商配置
- 工作流配置与 Cron 定时调度
- 文章收集、去重与分类
- 事件提取与归类
- 每日摘要生成
- 任务日志与监控
- 系统统计仪表盘

## 环境变量

所有可用的配置选项请参见 `.env.example`。

关键变量：
- `DATABASE_URL`: PostgreSQL 连接字符串
- `REDIS_URL`: Redis 连接字符串
- `WECHAT_ADAPTER_URL`: 微信侧车服务 URL
- `ENCRYPTION_KEY`: 32 字节十六进制密钥，用于 API 密钥加密
- `SECRET_KEY`: 应用密钥

## 许可证

MIT

## 鸣谢

- [wechat-download-api](https://github.com/tmwks/wechat-download-api) — 微信公众号文章采集适配器
