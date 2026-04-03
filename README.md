# 微信新闻智能体

一个本地自托管的微信智能简报系统。自动从微信公众号采集文章，通过 LLM 生成每日摘要，并推送到飞书群或邮箱。

## 功能特性

- **公众号管理** — 添加目标公众号，一键搜索并填充 fakeid
- **关键词管理** — 按行业、公司、事件分类，支持权重
- **文章采集** — 自动从公众号抓取文章全文，按关键词过滤
- **文章分类** — LLM 自动分析文章相关性、事件类型、标签、公司，生成摘要
- **每日摘要** — LLM 生成结构化日报，支持主题分组与编辑观点
- **飞书推送** — 配置群机器人 Webhook，一键或自动发送摘要
- **邮件推送** — 配置 SMTP，发送 HTML 格式摘要到指定邮箱
- **工作流调度** — APScheduler 定时任务，实时查看运行状态
- **模型配置** — 兼容 OpenAI 接口的任意 LLM 提供商
- **RSS 采集** — 支持从 RSS 源采集文章

## 快速开始

### 前置条件

- Docker + Docker Compose
- 支持 Linux、macOS、Windows (WSL 2)

### 1. 克隆与配置

```bash
# 克隆项目
git clone <your-repo-url>
cd wx_news_agent

# 复制环境配置
cp .env.example .env

# 生成加密密钥
python3 -c "import secrets; print(secrets.token_hex(32))"
# 将结果填入 .env 中的 ENCRYPTION_KEY

python3 -c "import secrets; print(secrets.token_hex(32))"
# 将结果填入 .env 中的 SECRET_KEY
```

### 2. 启动服务

```bash
docker compose up -d
```

启动后可访问：

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

## 使用指南

### 第一步：微信登录

1. 进入 **微信登录** 页面
2. 用微信扫描二维码登录
3. 确认登录状态显示为"已登录"

> 微信登录态有过期时间，如采集失败请重新扫码。

### 第二步：添加公众号

1. 进入 **公众号管理** 页面
2. 点击"添加公众号"，填写名称等信息
3. 点击每行右侧的 🔍 搜索图标
4. 输入公众号名称搜索，从结果中点击匹配项自动填充 fakeid

> fakeid 是微信内部标识符，必须通过搜索获取。不设置 fakeid 的公众号无法采集文章。

### 第三步：设置关键词

1. 进入 **关键词管理** 页面
2. 添加你关注的关键词，选择类型（行业/公司/事件）和权重
3. 采集到的文章如果标题或摘要包含任一关键词，会被标记为"相关"

> 不设置关键词时，所有采集到的文章都会保留但不标记相关性。

### 第四步：配置 LLM 提供商

1. 进入 **模型配置** 页面
2. 点击"添加提供商"，填写：
   - 名称（如 onehub、openai）
   - API 地址（如 `https://api.openai.com/v1`）
   - API Key
   - 默认模型（如 `gpt-4o`）
3. 勾选"用于摘要生成"（生成每日摘要时使用此模型）
4. 点击"测试"验证连通性

### 第五步：运行工作流

进入 **工作流** 页面，可以看到预设的工作流：

| 工作流 | 说明 | 默认调度 |
|--------|------|----------|
| 每日采集 | 从公众号采集文章全文，按关键词过滤 | 每天 8:00 |
| 文章分类 | 对已采集但未分类的文章进行 LLM 分类与摘要生成 | 每 30 分钟 |
| 生成摘要 | 基于当日文章生成每日摘要 | 每天 20:00 |
| 登录检查 | 检查微信登录状态 | 每 2 小时 |
| RSS采集 | 从 RSS 源采集文章全文 | 每小时 |

点击 ▶ 立即运行，按钮会变为旋转图标，下方显示"运行中..."。完成后自动更新上次运行时间和状态。

### 第六步：查看文章与摘要

进入 **文章列表** 页面：
- 查看所有采集到的文章，支持按来源、状态、相关性、事件类型筛选
- 点击"查看"按钮展开 LLM 生成的摘要、标签、公司、事件类型和相关性评分
- 点击文章标题可在新窗口阅读原文

进入 **每日摘要** 页面：
- 左侧是历史摘要列表
- 右侧可切换"渲染"（排版后的 Markdown）和"源码"（原始 Markdown）视图
- 相关文章标题为可点击链接

### 第七步：推送摘要

生成每日摘要后，可一键推送到以下平台（也支持配置自动生成后自动推送）：

- **飞书** — 通过群机器人 Webhook 推送
- **邮件** — 通过 SMTP 发送 HTML 格式邮件

## 项目结构

```
wx_news_agent/
├── apps/
│   ├── web/                  # Next.js 前端
│   └── api/                  # FastAPI 后端 (含 APScheduler 定时任务)
├── infra/
│   └── nginx/                # Nginx 反向代理 (可选)
├── docker-compose.yml
├── .env.example
└── README.md
```

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Next.js 15 + TypeScript + Tailwind CSS + React Query |
| 后端 API | FastAPI (Python 3.13) |
| 定时任务 | APScheduler |
| 数据库 | SQLite |
| 微信适配器 | wechat-download-api |
| RSS 解析 | feedparser |
| LLM | OpenAI 兼容接口（任意提供商） |

## 开发

### 前端

```bash
cd apps/web
npm install
npm run dev
```

### 后端

```bash
cd apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload
```

> 定时任务会在 API 启动时自动注册，无需额外启动 worker。

## 环境变量

详见 `.env.example`。关键变量：

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | 数据库连接（默认 `sqlite:///./data/embodied_news.db`） |
| `WECHAT_ADAPTER_URL` | 微信适配器服务 URL |
| `ENCRYPTION_KEY` | 32 字节十六进制密钥，用于加密 API Key 等敏感信息 |
| `SECRET_KEY` | 应用密钥 |

## 许可证

本项目采用 GNU Affero General Public License v3.0 (AGPL-3.0) 许可证。

本项目使用了以下开源项目：

- [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api) — 微信公众号文章采集适配器

## 鸣谢

- [wechat-download-api](https://github.com/tmwgsicp/wechat-download-api) — 微信公众号文章采集适配器
