# Embodied News Agent

A local, self-hosted WeChat intelligence briefing system running on Windows + WSL.

## Architecture

- **Frontend**: Next.js 15 + TypeScript + Tailwind CSS
- **Backend API**: FastAPI (Python 3.11+)
- **Task Queue**: Celery + Redis + Celery Beat
- **Database**: PostgreSQL 16
- **WeChat Adapter**: Sidecar service (wechat-download-api)
- **LLM Gateway**: OpenAI-compatible provider abstraction

## Quick Start

### Prerequisites

- Windows with WSL 2 (Ubuntu recommended)
- Docker Desktop with WSL 2 backend
- Code directory inside WSL filesystem (NOT /mnt/c/...)

### Setup

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Generate encryption key (32 bytes hex)
python3 -c "import secrets; print(secrets.token_hex(32))"
# Update ENCRYPTION_KEY in .env

# 3. Generate secret key
python3 -c "import secrets; print(secrets.token_hex(32))"
# Update SECRET_KEY in .env

# 4. Start all services
docker compose up -d

# 5. Access the application
# Frontend: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Development

### Frontend (Next.js)

```bash
cd apps/web
npm install
npm run dev
```

### Backend (FastAPI)

```bash
cd apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Worker (Celery)

```bash
cd apps/worker
pip install -r requirements.txt
celery -A app.worker worker --loglevel=info
celery -A app.worker beat --loglevel=info
```

## Project Structure

```
embodied-news-agent/
├── apps/
│   ├── web/                  # Next.js frontend
│   ├── api/                  # FastAPI backend
│   └── worker/               # Celery worker + beat
├── packages/
│   └── prompt-templates/     # LLM prompt templates
├── infra/
│   ├── docker/               # Docker configurations
│   └── nginx/                # Nginx reverse proxy
├── docs/                     # Documentation
├── data/                     # Local data files
├── docker-compose.yml
├── .env.example
└── README.md
```

## Features

- WeChat login status management
- Source account (公众号) whitelist management
- Keyword management with types and weights
- OpenAI-compatible model provider configuration
- Workflow configuration with cron scheduling
- Article collection, deduplication, and classification
- Event extraction and categorization
- Daily digest generation
- Task logging and monitoring
- Dashboard with system stats

## Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `WECHAT_ADAPTER_URL`: WeChat sidecar service URL
- `ENCRYPTION_KEY`: 32-byte hex key for API key encryption
- `SECRET_KEY`: Application secret key

## License

Private
