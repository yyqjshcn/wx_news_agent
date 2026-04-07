# 微信新闻智能体 — 详细指南

> 本文档是 README 的扩展版，深入讲解系统架构、工作流逻辑、Prompt 配置、邮件模板和推送系统。

---

## 目录

1. [系统架构概览](#1-系统架构概览)
2. [数据模型详解](#2-数据模型详解)
3. [工作流详解](#3-工作流详解)
4. [Prompt 配置指南](#4-prompt-配置指南)
5. [邮件模板配置指南](#5-邮件模板配置指南)
6. [推送系统详解](#6-推送系统详解)

---

## 1. 系统架构概览

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户界面层                                │
│                    Next.js 前端 (localhost:3000)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP
┌────────────────────────────▼────────────────────────────────────┐
│                       API 服务层                                 │
│              FastAPI 后端 (localhost:8000)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  REST API    │  │ APScheduler  │  │  微信适配器通信        │  │
│  │  (路由层)    │  │ (定时任务)   │  │  (wechat-download-api) │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬───────────┘  │
│         │                 │                       │              │
│  ┌──────▼─────────────────▼───────────────────────▼───────────┐  │
│  │                    业务逻辑层                                │  │
│  │  采集逻辑 │ 分类逻辑 │ 摘要生成 │ 推送逻辑 │ Prompt 加载    │  │
│  └────────────────────────┬───────────────────────────────────┘  │
└────────────────────────────┼─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│                        数据层                                     │
│                      SQLite 数据库                                │
│  SourceAccount │ Keyword │ RawArticle │ DailyDigest │ Workflow   │
│  LlmProvider   │ RssFeed │ CuratedEvent │ EmailConfig │ ...      │
└──────────────────────────────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         ┌────────┐   ┌──────────┐   ┌──────────┐
         │ 飞书群  │   │ SMTP 邮箱│   │ 外部 LLM  │
         │ Webhook│   │ 服务器   │   │ API      │
         └────────┘   └──────────┘   └──────────┘
```

### 1.2 数据流向

```
SourceAccount ──┐
                ├──► daily_ingest ──► RawArticle (status="new")
Keyword ────────┘                        │
                                         │
RssFeed ────────┐                        │
                ├──► rss_ingest ─────────┘
Keyword ────────┘

RawArticle (status="new") ──► classify_pending_articles
                                   │
                                   ▼
                            RawArticle (status="classified")
                                   │
                                   ├──► CuratedEvent (自动创建)
                                   │
                                   ▼
                            generate_daily_digest
                                   │
                                   ▼
                              DailyDigest
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
               飞书 Webhook   SMTP 邮件      前端展示
```

### 1.3 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 前端 | Next.js 15 + TypeScript + Tailwind CSS + React Query | SPA 管理界面 |
| 后端 API | FastAPI (Python 3.13) | RESTful API |
| 定时任务 | APScheduler (AsyncIOScheduler) | 进程内调度，支持 cron 表达式 |
| 数据库 | SQLite | 轻量嵌入式数据库 |
| 微信采集 | wechat-download-api | 外部适配器服务 |
| RSS 解析 | feedparser | RSS/Atom 源解析 |
| LLM | OpenAI 兼容接口 | 支持任意提供商 |
| 邮件 | smtplib + email (Python 标准库) | SMTP 发送 |
| 加密 | Fernet (cryptography) | API Key 等敏感信息加密 |

### 1.4 核心组件关系

```
apps/api/
├── app/
│   ├── api/              # REST API 路由
│   │   ├── source_accounts.py
│   │   ├── keywords.py
│   │   ├── articles.py
│   │   ├── digests.py
│   │   ├── llm_providers.py
│   │   ├── workflows.py
│   │   ├── rss_feeds.py
│   │   ├── feishu_webhooks.py
│   │   ├── email_configs.py
│   │   ├── notification_channels.py
│   │   └── ...
│   ├── core/
│   │   ├── prompt_loader.py   # Prompt / 模板加载器
│   │   └── scheduler.py       # APScheduler 核心逻辑
│   ├── models/            # SQLAlchemy 数据模型
│   ├── services/
│   │   ├── email_service.py           # 旧版邮件服务
│   │   ├── feishu_service.py          # 旧版飞书服务
│   │   └── notification_service.py    # 统一通知服务
│   └── db/
│       └── base.py        # ORM 基类
├── prompts/               # Prompt 模板文件
│   ├── classify.json
│   ├── classify.template.json
│   ├── digest.json
│   └── digest.template.json
└── templates/             # 邮件 HTML 模板
    ├── email.html
    └── email.template.html
```

---

## 2. 数据模型详解

> 所有模型使用 UUID 字符串作为主键，继承自 `DeclarativeBase`。模型间通过字符串 ID 建立隐式关联，无显式 `ForeignKey` 或 `relationship()`。

### 2.1 RawArticle — 原始文章

存储从公众号或 RSS 采集到的文章全文及分类结果。

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | String (UUID) | `uuid4()` | 主键 |
| `article_url` | String | — | 文章 URL（唯一约束） |
| `title` | String | — | 文章标题 |
| `account_name` | String | — | 来源公众号名称 |
| `source_type` | String | `"wechat"` | 来源类型：`wechat` 或 `rss` |
| `fakeid` | String | — | 微信公众号 fakeid |
| `publish_time` | DateTime(tz) | — | 原始发布时间 |
| `author` | String | — | 文章作者 |
| `plain_content` | Text | — | 纯文本内容 |
| `html_content` | Text | — | HTML 内容 |
| `content_hash` | String | — | 去重哈希（`sha256(title + link)`） |
| `title_normalized` | String | — | 标准化后的标题 |
| `fetched_at` | DateTime(tz) | `now(utc)` | 采集时间 |
| `status` | String | `"new"` | 处理状态：`new` → `classified` |
| `is_relevant` | Boolean | — | 是否相关（关键词匹配或 LLM 判断） |
| `relevance_score` | Float | — | 相关性评分（0-10） |
| `primary_event_type` | String | — | 事件类型（如"融资"、"产品发布"） |
| `tags_json` | JSON | `[]` | 标签列表 |
| `companies_json` | JSON | `[]` | 涉及公司列表 |
| `summary_short` | Text | — | 一句话摘要 |
| `summary_long` | Text | — | 详细摘要（3-5 句） |
| `llm_provider_id` | String | — | 分类使用的 LLM 提供商 ID |
| `llm_model` | String | — | 使用的模型名称 |
| `raw_llm_output_json` | JSON | — | LLM 原始输出（调试用） |
| `created_at` | DateTime(tz) | `now(utc)` | 创建时间 |
| `updated_at` | DateTime(tz) | `now(utc)` | 更新时间 |

### 2.2 SourceAccount — 公众号

管理目标微信公众号账号。

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | String (UUID) | `uuid4()` | 主键 |
| `account_name` | String | — | 公众号显示名称 |
| `account_alias` | String | — | 别名/简称 |
| `fakeid` | String | — | 微信内部标识符（必须通过搜索获取） |
| `category` | String | — | 分类 |
| `priority` | Integer | `5` | 采集优先级 |
| `enabled` | Boolean | `True` | 是否启用 |
| `last_checked_at` | DateTime(tz) | — | 上次采集时间 |
| `last_success_at` | DateTime(tz) | — | 上次成功采集时间 |
| `notes` | Text | — | 备注 |
| `created_at` | DateTime(tz) | `now(utc)` | 创建时间 |
| `updated_at` | DateTime(tz) | `now(utc)` | 更新时间 |

### 2.3 RssFeed — RSS 源

管理 RSS 订阅源。

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | String (UUID) | `uuid4()` | 主键 |
| `name` | String | — | 显示名称 |
| `feed_url` | String | — | RSS/Atom 源 URL |
| `category` | String | — | 分类 |
| `priority` | Integer | `5` | 采集优先级 |
| `enabled` | Boolean | `True` | 是否启用 |
| `last_checked_at` | DateTime(tz) | — | 上次采集时间 |
| `last_success_at` | DateTime(tz) | — | 上次成功采集时间 |
| `notes` | Text | — | 备注 |
| `created_at` | DateTime(tz) | `now(utc)` | 创建时间 |
| `updated_at` | DateTime(tz) | `now(utc)` | 更新时间 |

### 2.4 Keyword — 关键词

用于文章相关性过滤的关键词配置。

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | String (UUID) | `uuid4()` | 主键 |
| `keyword` | String | — | 关键词文本 |
| `keyword_type` | String | `"industry"` | 类型：`industry`（行业）/ `company`（公司）/ `event`（事件） |
| `weight` | Integer | `1` | 权重 |
| `enabled` | Boolean | `True` | 是否启用 |
| `notes` | Text | — | 备注 |
| `created_at` | DateTime(tz) | `now(utc)` | 创建时间 |
| `updated_at` | DateTime(tz) | `now(utc)` | 更新时间 |

### 2.5 LlmProvider — LLM 提供商

配置 LLM 服务连接信息。

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | String (UUID) | `uuid4()` | 主键 |
| `name` | String | — | 显示名称 |
| `provider_type` | String | `"openai_compatible"` | 类型（当前仅支持 `openai_compatible`） |
| `base_url` | String | — | API 地址（如 `https://api.openai.com/v1`） |
| `api_key_encrypted` | Text | — | 加密后的 API Key（Fernet 加密） |
| `default_model` | String | — | 默认模型名称 |
| `enabled` | Boolean | `True` | 是否启用 |
| `is_default_for_relevance` | Boolean | `False` | 是否用于相关性判断 |
| `is_default_for_extraction` | Boolean | `False` | 是否用于信息提取（文章分类） |
| `is_default_for_digest` | Boolean | `False` | 是否用于摘要生成 |
| `request_timeout` | Integer | `30` | 请求超时（秒） |
| `max_retries` | Integer | `3` | 最大重试次数 |
| `extra_headers_json` | JSON | `{}` | 额外 HTTP 请求头 |
| `extra_query_json` | JSON | `{}` | 额外查询参数 |
| `last_test_status` | String | — | 上次测试状态 |
| `last_test_message` | Text | — | 上次测试消息 |
| `last_test_at` | DateTime(tz) | — | 上次测试时间 |
| `created_at` | DateTime(tz) | `now(utc)` | 创建时间 |
| `updated_at` | DateTime(tz) | `now(utc)` | 更新时间 |

### 2.6 Workflow — 工作流定义

定义定时任务的调度规则。

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | String (UUID) | `uuid4()` | 主键 |
| `workflow_name` | String | — | 显示名称 |
| `workflow_type` | Enum | — | 工作流类型（见下方枚举） |
| `enabled` | Boolean | `True` | 是否启用 |
| `cron_expression` | String | — | cron 表达式（5 字段） |
| `timezone` | String | `"Asia/Shanghai"` | 时区 |
| `config_json` | JSON | `{}` | 工作流配置 |
| `last_run_at` | DateTime(tz) | — | 上次运行时间 |
| `last_status` | String | — | 上次运行状态 |
| `created_at` | DateTime(tz) | `now(utc)` | 创建时间 |
| `updated_at` | DateTime(tz) | `now(utc)` | 更新时间 |

**WorkflowType 枚举值：**

| 枚举值 | 说明 |
|---|---|
| `daily_ingest` | 每日采集（微信） |
| `midday_refresh` | 午间刷新（复用采集逻辑） |
| `classify_pending_articles` | 待分类文章处理 |
| `generate_daily_digest` | 每日摘要生成 |
| `retry_failed_jobs` | 失败重试（复用采集逻辑） |
| `login_health_check` | 微信登录检查 |
| `rss_ingest` | RSS 采集 |

### 2.7 WorkflowRun — 工作流运行记录

记录每次工作流执行的详细信息。

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | String (UUID) | `uuid4()` | 主键 |
| `workflow_id` | String | — | 所属工作流 ID |
| `trigger_type` | Enum | — | 触发类型：`scheduled` / `manual` / `retry` |
| `status` | Enum | `pending` | 运行状态：`pending` → `running` → `success` / `failed` |
| `started_at` | DateTime(tz) | — | 开始时间 |
| `finished_at` | DateTime(tz) | — | 结束时间 |
| `duration_ms` | Integer | — | 执行时长（毫秒） |
| `error_message` | Text | — | 错误信息 |
| `summary_json` | JSON | `{}` | 运行摘要（结构化数据） |
| `created_at` | DateTime(tz) | `now(utc)` | 创建时间 |

### 2.8 DailyDigest — 每日摘要

存储 LLM 生成的每日摘要。

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | String (UUID) | `uuid4()` | 主键 |
| `digest_date` | DateTime(tz) | — | 摘要日期 |
| `content_markdown` | Text | — | Markdown 格式内容 |
| `content_html` | Text | — | HTML 格式内容 |
| `item_count` | Integer | `0` | 文章数量 |
| `status` | String | `"draft"` | 状态：`draft` → `published` → `sent` |
| `llm_provider_id` | String | — | 使用的 LLM 提供商 ID |
| `llm_model` | String | — | 使用的模型名称 |
| `generated_at` | DateTime(tz) | — | 生成时间 |
| `sent_at` | DateTime(tz) | — | 推送时间 |
| `created_at` | DateTime(tz) | `now(utc)` | 创建时间 |
| `updated_at` | DateTime(tz) | `now(utc)` | 更新时间 |

### 2.9 CuratedEvent — 策划事件

从文章分类结果中自动创建的事件记录。

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | String (UUID) | `uuid4()` | 主键 |
| `article_id` | String | — | 关联文章 ID |
| `company_name` | String | — | 相关公司 |
| `event_type` | String | — | 事件类型 |
| `importance` | Integer | `3` | 重要程度（1-5） |
| `one_line_summary` | Text | — | 一句话摘要 |
| `analyst_note` | Text | — | 分析师备注（人工填写） |
| `included_in_digest` | Boolean | `False` | 是否已纳入摘要 |
| `event_date` | DateTime(tz) | — | 事件日期 |
| `created_at` | DateTime(tz) | `now(utc)` | 创建时间 |
| `updated_at` | DateTime(tz) | `now(utc)` | 更新时间 |

### 2.10 EmailConfig — 邮件配置（旧版）

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | String (UUID) | `uuid4()` | 主键 |
| `name` | String | — | 显示名称 |
| `smtp_host` | String | — | SMTP 服务器地址 |
| `smtp_port` | Integer | `587` | SMTP 端口 |
| `use_tls` | Boolean | `True` | 是否使用 STARTTLS |
| `sender_email` | String | — | 发件人邮箱 |
| `sender_name` | String | `"每日摘要"` | 发件人显示名称 |
| `sender_password` | Text | — | SMTP 密码（Fernet 加密） |
| `recipients_json` | JSON | `[]` | 收件人列表 |
| `enabled` | Boolean | `True` | 是否启用 |
| `send_on_digest_generated` | Boolean | `False` | 摘要生成后自动发送（**当前未实现**） |
| `created_at` | DateTime(tz) | `now(utc)` | 创建时间 |
| `updated_at` | DateTime(tz) | `now(utc)` | 更新时间 |

### 2.11 FeishuWebhook — 飞书 Webhook（旧版）

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | String (UUID) | `uuid4()` | 主键 |
| `name` | String | — | 显示名称 |
| `webhook_url` | Text | — | 飞书群机器人 Webhook URL |
| `enabled` | Boolean | `True` | 是否启用 |
| `send_on_digest_generated` | Boolean | `False` | 摘要生成后自动发送（**当前未实现**） |
| `message_title` | String | `"每日摘要"` | 消息卡片标题 |
| `include_source_links` | Boolean | `True` | 是否包含来源链接 |
| `extra_headers_json` | JSON | `{}` | 额外 HTTP 请求头 |
| `created_at` | DateTime(tz) | `now(utc)` | 创建时间 |
| `updated_at` | DateTime(tz) | `now(utc)` | 更新时间 |

### 2.12 NotificationChannel — 统一通知渠道

支持 7 种渠道类型的统一抽象。

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | String (UUID) | `uuid4()` | 主键 |
| `alias` | String | — | 唯一别名 |
| `name` | String | — | 显示名称 |
| `channel_type` | String | — | 渠道类型（见下方列表） |
| `enabled` | Boolean | `True` | 是否启用 |
| `send_on_digest_generated` | Boolean | `False` | 摘要生成后自动发送（**当前未实现**） |
| `config_json` | JSON | `{}` | 渠道特定配置 |
| `created_at` | DateTime(tz) | `now(utc)` | 创建时间 |
| `updated_at` | DateTime(tz) | `now(utc)` | 更新时间 |

**支持的渠道类型：**

| 类型 | 说明 |
|---|---|
| `feishu` | 飞书群机器人 |
| `wechat_work` | 企业微信 |
| `dingtalk` | 钉钉 |
| `slack` | Slack |
| `discord` | Discord |
| `custom_webhook` | 自定义 Webhook |
| `email` | 邮件 |

### 2.13 LoginSession — 微信登录会话

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | String (UUID) | `uuid4()` | 主键 |
| `provider_name` | String | `"wechat"` | 登录提供商 |
| `status` | String | `"unknown"` | 会话状态 |
| `last_checked_at` | DateTime(tz) | — | 上次检查时间 |
| `last_success_at` | DateTime(tz) | — | 上次成功登录时间 |
| `expires_at` | DateTime(tz) | — | 过期时间 |
| `message` | Text | — | 状态消息 |
| `metadata_json` | Text | — | 额外元数据 |
| `created_at` | DateTime(tz) | `now(utc)` | 创建时间 |
| `updated_at` | DateTime(tz) | `now(utc)` | 更新时间 |

### 2.14 SystemLog — 系统日志

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `id` | String (UUID) | `uuid4()` | 主键 |
| `level` | String | `"INFO"` | 日志级别 |
| `module` | String | — | 来源模块 |
| `message` | Text | — | 日志消息 |
| `payload_json` | JSON | `{}` | 结构化负载 |
| `created_at` | DateTime(tz) | `now(utc)` | 创建时间 |

### 2.15 模型关系图

```
SourceAccount (1) ──────< (N) RawArticle (N) >────── CuratedEvent (1)
                                                        │
RssFeed (1) ──────────< (N) RawArticle                  │
                                                        │
Keyword ──(用于过滤)──► RawArticle                      │
                                                        │
LlmProvider (1) ──< (N) RawArticle                     │
       │                                                │
       └──< (N) DailyDigest                             │
                                                        │
Workflow (1) ────< (N) WorkflowRun                      │
                                                        │
                                                        │
RawArticle (1) ──< (N) CuratedEvent ────────────────────┘
```

---

## 3. 工作流详解

### 3.1 调度机制

系统使用 **APScheduler**（`AsyncIOScheduler`）作为工作流引擎，运行在 FastAPI 进程内，无需独立 worker。

#### 调度器生命周期

```
API 启动
  │
  ▼
start_scheduler()
  │
  ├── 创建 AsyncIOScheduler 实例
  ├── 从数据库加载所有 enabled=True 的 Workflow
  ├── 为每个 Workflow 注册 cron job（job ID: workflow_{id}）
  ├── 启动调度器
  │
  └── 注册自动重载任务（每 60 秒执行一次）
        │
        ▼
      reload_scheduler_workflows()
        │
        ├── 检测新增的 Workflow → add_workflow_to_scheduler()
        ├── 检测已禁用的 Workflow → remove_workflow_from_scheduler()
        └── 检测已修改的 Workflow → update_workflow_in_scheduler()
```

#### 工作流执行流程

**定时触发：**
```
APScheduler cron 触发
  │
  ▼
run_workflow_task(workflow_id, TriggerType.SCHEDULED)
  │
  ├── 查询 Workflow 记录
  ├── 从 TASK_MAP 查找对应的执行函数
  ├── 创建 WorkflowRun（status=PENDING）
  │
  ▼
_execute_workflow(run_id, type, task_fn)
  │
  ├── _mark_run_started() → status=RUNNING, started_at=now
  │
  ├── task_fn(workflow_id) → 执行实际逻辑 → 返回 summary dict
  │
  └── _mark_run_finished() → status=SUCCESS/FAILED
       ├── finished_at = now
       ├── duration_ms = 计算耗时
       └── summary_json = 运行摘要
```

**手动触发：**
```
POST /api/workflows/{id}/run
  │
  ├── 查询 Workflow 记录
  ├── 从 TASK_MAP 查找对应的执行函数
  ├── 创建 WorkflowRun（status=PENDING）
  │
  ▼
schedule_workflow_run() → asyncio.create_task()
  │
  ├── 更新状态为 RUNNING
  ├── _execute_workflow() → 后台执行
  └── 完成后更新状态为 SUCCESS/FAILED
```

#### TASK_MAP 映射

| 工作流类型 | 执行函数 | 说明 |
|---|---|---|
| `daily_ingest` | `do_daily_ingest` | 微信公众号文章采集 |
| `midday_refresh` | `do_daily_ingest` | 复用采集逻辑 |
| `retry_failed_jobs` | `do_daily_ingest` | 复用采集逻辑 |
| `rss_ingest` | `do_rss_ingest` | RSS 源文章采集 |
| `classify_pending_articles` | `do_classify_articles` | LLM 文章分类 |
| `generate_daily_digest` | `do_generate_digest` | 每日摘要生成 |
| `login_health_check` | `do_login_health_check` | 登录状态检查（存根） |

---

### 3.2 daily_ingest — 每日采集（微信）

**触发方式：** 定时（cron 表达式）或手动 API 调用

**执行函数：** `do_daily_ingest`

#### 执行流程

```
开始
  │
  ▼
1. 查询所有 enabled=True 且 fakeid 不为空的 SourceAccount
  │
  ▼
2. 查询所有 enabled=True 的 Keyword
  │
  ▼
3. 若无账号 → 提前返回（articles_fetched=0）
  │
  ▼
4. 遍历每个 SourceAccount：
  │
  ├── 4a. 调用微信适配器获取文章列表
  │     GET {WECHAT_ADAPTER_URL}/api/public/articles?fakeid={fakeid}&begin=0&count=20
  │
  ├── 4b. 遍历返回的每篇文章：
  │     │
  │     ├── 提取：title, link, author, digest, update_time
  │     │
  │     ├── 关键词匹配：
  │     │   检查 (title + digest).lower() 是否包含任一 keyword.keyword
  │     │   → 匹配则 is_relevant=True
  │     │
  │     ├── 计算 content_hash = sha256(title + link)
  │     │
  │     ├── 去重检查：
  │     │   若 article_url 已存在于 RawArticle → 跳过
  │     │
  │     ├── 获取全文：
  │     │   POST {WECHAT_ADAPTER_URL}/api/article {"url": link}
  │     │   → 获取 plain_content 和 html_content
  │     │
  │     └── 创建 RawArticle 记录：
  │         status="new", source_type="wechat"
  │
  ├── 4c. 更新 SourceAccount：
  │     last_checked_at = now
  │     last_success_at = now
  │
  └── 4d. 若出错 → 记录错误，继续处理下一个账号
  │
  ▼
5. 返回运行摘要：
   {
     "articles_fetched": 采集文章数,
     "articles_stored": 入库文章数,
     "articles_matched_keyword": 关键词匹配数,
     "sources_processed": 处理的公众号数,
     "errors": 错误列表
   }
```

#### 读取/写入的数据

| 操作 | 模型 | 说明 |
|---|---|---|
| 读取 | `SourceAccount` | 获取启用的公众号列表 |
| 读取 | `Keyword` | 获取关键词用于匹配 |
| 写入 | `RawArticle` | 存储新采集的文章 |
| 更新 | `SourceAccount` | 更新 last_checked_at / last_success_at |

#### 外部调用

| 端点 | 方法 | 用途 |
|---|---|---|
| `{WECHAT_ADAPTER_URL}/api/public/articles` | GET | 获取文章列表 |
| `{WECHAT_ADAPTER_URL}/api/article` | POST | 获取文章全文 |

#### 错误处理

- 每个公众号独立 try/catch，单个失败不影响其他公众号
- 错误收集到 errors 列表，最终汇总报告
- 若所有公众号都失败或采集数为 0 → 状态标记为 `failed`

---

### 3.3 rss_ingest — RSS 采集

**触发方式：** 定时（cron 表达式）或手动 API 调用

**执行函数：** `do_rss_ingest`

#### 执行流程

```
开始
  │
  ▼
1. 查询所有 enabled=True 的 RssFeed
  │
  ▼
2. 查询所有 enabled=True 的 Keyword
  │
  ▼
3. 若无 feed → 提前返回
  │
  ▼
4. 遍历每个 RssFeed：
  │
  ├── 4a. 解析 RSS 源：
  │     feedparser.parse(feed_url)
  │
  ├── 4b. 遍历每个 entry（最多 50 条）：
  │     │
  │     ├── 提取：title, link, author, published, content
  │     │
  │     ├── 关键词匹配：
  │     │   检查 (title + content).lower() 是否包含任一 keyword.keyword
  │     │
  │     ├── 去重检查：
  │     │   若 article_url 已存在 → 跳过
  │     │
  │     ├── 获取全文：
  │     │   GET {link} → 用 lxml 去除 HTML 标签
  │     │   提取 <article>、<main> 或 body 内的文本
  │     │   截取最多 10,000 字符
  │     │
  │     └── 创建 RawArticle 记录：
  │         status="new", source_type="rss"
  │
  ├── 4c. 更新 RssFeed：
  │     last_checked_at = now
  │     last_success_at = now
  │
  └── 4d. 若出错 → 记录错误，继续处理下一个 feed
  │
  ▼
5. 返回运行摘要（同 daily_ingest）
```

#### 读取/写入的数据

| 操作 | 模型 | 说明 |
|---|---|---|
| 读取 | `RssFeed` | 获取启用的 RSS 源列表 |
| 读取 | `Keyword` | 获取关键词用于匹配 |
| 写入 | `RawArticle` | 存储新采集的文章 |
| 更新 | `RssFeed` | 更新 last_checked_at / last_success_at |

---

### 3.4 classify_pending_articles — 文章分类

**触发方式：** 定时（cron 表达式）或手动 API 调用

**执行函数：** `do_classify_articles`

#### 执行流程

```
开始
  │
  ▼
1. 查找 LLM 提供商：
   优先：enabled=True AND is_default_for_extraction=True
   备选：任意 enabled=True 的提供商
   │
  ▼
2. 若无提供商 → 提前返回（classified_count=0）
  │
  ▼
3. 批量处理循环：
   │
   ├── 3a. 检查工作流超时（最长 30 分钟）
   │
   ├── 3b. 查询最多 10 条 status="new" 的 RawArticle
   │     按 created_at ASC 排序
   │
   ├── 3c. 若无待分类文章 → 退出循环
   │
   ├── 3d. 并发处理这批文章（信号量=3，每篇超时 120 秒）：
   │     │
   │     ├── _classify_article_async(article, provider):
   │     │   │
   │     │   ├── 解密 API Key
   │     │   │
   │     │   ├── 加载 Prompt：load_prompt("classify")
   │     │   │   优先读取 classify.json，否则 classify.template.json
   │     │   │
   │     │   ├── 构建 Prompt：
   │     │   │   取文章 80% 的内容
   │     │   │   填充 {title}, {account_name}, {content}, {relevance_criteria}
   │     │   │
   │     │   ├── 调用 LLM：
   │     │   │   POST {base_url}/chat/completions
   │     │   │   含 system_prompt + user_prompt
   │     │   │
   │     │   ├── 解析响应：
   │     │   │   尝试解析 JSON（支持去除 markdown 代码块）
   │     │   │   失败则指数退避重试（2^attempt 秒）
   │     │   │   最大重试后仍失败 → 返回 fallback（is_relevant=None）
   │     │   │
   │     │   └── 返回分类结果
   │     │
   │     ├── 更新 RawArticle：
   │     │   is_relevant, relevance_score, primary_event_type,
   │     │   tags_json, companies_json, summary_short, summary_long,
   │     │   status="classified", llm_provider_id, llm_model
   │     │
   │     └── 自动创建 CuratedEvent：
   │         若 event_type 或 companies 存在
   │         每篇文章最多创建 5 个事件（每个公司一个）
   │
   ├── 3e. 提交数据库事务
   │
   └── 3f. 回到 3a 继续下一批
  │
  ▼
4. 返回运行摘要：
   {
     "classified_count": 分类文章数,
     "total_errors": 错误总数,
     "errors": 错误列表（最多 10 条）
   }
```

#### 读取/写入的数据

| 操作 | 模型 | 说明 |
|---|---|---|
| 读取 | `LlmProvider` | 获取分类用 LLM 配置 |
| 读取 | `RawArticle` | 查询 status="new" 的文章 |
| 写入 | `RawArticle` | 更新分类字段，status → "classified" |
| 写入 | `CuratedEvent` | 自动创建事件记录 |

#### LLM 调用详情

- **Prompt 文件：** `classify.json` 或 `classify.template.json`
- **每篇文章一次调用**
- **并发限制：** 最多 3 篇同时处理
- **单篇超时：** 120 秒
- **重试策略：** 指数退避（2^attempt 秒），最多 `max_retries` 次
- **Fallback：** JSON 解析失败后返回 `is_relevant=None` 的安全结果

#### 错误处理

- 单篇文章：120 秒超时 + 指数退避重试 + 优雅降级
- 批次级别：`asyncio.gather` 收集所有结果
- 整体：30 分钟工作流超时
- 状态判定：
  - 0 篇分类且有错误 → `failed`
  - 部分有错误 → `partial`
  - 全部成功 → `completed`

---

### 3.5 generate_daily_digest — 每日摘要生成

**触发方式：** 定时（cron 表达式）或手动 API 调用

**执行函数：** `do_generate_digest`

#### 执行流程

```
开始
  │
  ▼
1. 计算日期范围（北京时间 UTC+8）：
   today, yesterday, tomorrow
  │
  ▼
2. 文章选择（级联回退策略）：
   │
   ├── 优先：today 的 is_relevant=True 的文章
   ├── 若无 → yesterday 的 is_relevant=True 的文章
   ├── 若无 → today 的全部文章（最多 30 篇）
   └── 若无 → yesterday 的全部文章（最多 30 篇）
  │
  ▼
3. 查找摘要用 LLM 提供商：
   优先：enabled=True AND is_default_for_digest=True
   备选：任意 enabled=True 的提供商
  │
  ▼
4. 生成内容 _generate_digest_content(articles, provider):
   │
   ├── 若无文章：
   │   返回 "# 每日摘要\n\n今日暂无相关文章。"
   │
   ├── 若有提供商：
   │   │
   │   ├── 取前 20 篇文章
   │   │
   │   ├── 构建文章摘要列表（标题、链接、来源、short summary）
   │   │
   │   ├── 加载 Prompt：load_prompt("digest")
   │   │   优先读取 digest.json，否则 digest.template.json
   │   │
   │   ├── 填充 Prompt 变量：
   │   │   {article_count}, {top_count}, {focus_area}, {articles}
   │   │
   │   ├── 调用 LLM（同步）：
   │   │   POST {base_url}/chat/completions
   │   │   max_tokens=4000, timeout=120
   │   │
   │   ├── 修复 Markdown 标题格式
   │   │
   │   └── 组装最终内容：
   │       header（标题、日期、文章数）+ LLM 内容 + footer（模型名）
   │
   └── 若无提供商或 LLM 失败：
       按公众号分组，列出文章链接和 short summary
  │
  ▼
5. 若包含非相关文章，添加说明注释
  │
  ▼
6. Upsert DailyDigest：
   若当天已存在 → 更新 content_markdown 和 item_count
   若不存在 → 创建新记录
  │
  ▼
7. 返回运行摘要：
   {
     "digest_date": 摘要日期,
     "article_count": 使用的文章数,
     "llm_provider": 使用的提供商,
     "llm_model": 使用的模型
   }
```

#### 读取/写入的数据

| 操作 | 模型 | 说明 |
|---|---|---|
| 读取 | `RawArticle` | 按日期和相关性查询文章 |
| 读取 | `LlmProvider` | 获取摘要用 LLM 配置 |
| 写入 | `DailyDigest` | Upsert 每日摘要 |

#### LLM 调用详情

- **Prompt 文件：** `digest.json` 或 `digest.template.json`
- **每次工作流执行最多一次调用**
- **输入文章数：** 最多 20 篇
- **最大 token：** 4000
- **超时：** 120 秒
- **同步调用**（使用 httpx 同步客户端）

#### 错误处理

- LLM 调用失败 → 自动回退到非 LLM 格式化列表
- 不抛出异常，保证始终有摘要产出
- 无提供商配置时也能生成基础摘要

---

### 3.6 login_health_check — 登录检查

**触发方式：** 定时（cron 表达式）或手动 API 调用

**执行函数：** `do_login_health_check`

#### 执行流程

```
开始
  │
  ▼
返回存根结果：
{
  "status": "checked",
  "timestamp": 当前时间
}
```

> **注意：** 此工作流当前为存根实现，未包含实际的微信登录状态检查逻辑。

---

### 3.7 midday_refresh — 午间刷新

**触发方式：** 定时（cron 表达式）或手动 API 调用

**执行函数：** `do_daily_ingest`（复用 `daily_ingest` 逻辑）

与 `daily_ingest` 完全相同，仅工作流名称和调度时间不同。适用于需要在日间额外采集一次的场景。

---

### 3.8 retry_failed_jobs — 失败重试

**触发方式：** 定时（cron 表达式）或手动 API 调用

**执行函数：** `do_daily_ingest`（复用 `daily_ingest` 逻辑）

与 `daily_ingest` 完全相同，用于重新采集所有公众号的最新文章。

---

## 4. Prompt 配置指南

### 4.1 Prompt 加载机制

系统通过 `apps/api/app/core/prompt_loader.py` 中的 `load_prompt()` 函数加载 Prompt。

**加载优先级：**

```
1. apps/api/prompts/{name}.json          ← 自定义版本（优先）
2. apps/api/prompts/{name}.template.json ← 通用模板（回退）
```

**使用方式：**

1. 复制 `.template.json` 文件并重命名为 `.json`（去掉 `.template` 部分）
2. 修改 `.json` 文件中的内容
3. 系统会自动优先读取 `.json` 文件

> 自定义的 `.json` 文件不会被 git 跟踪，方便独立维护。

### 4.2 classify.json — 文章分类 Prompt

#### 文件结构

```json
{
  "system_prompt": "系统提示词",
  "user_prompt_template": "用户提示词模板（含占位符）",
  "relevance_criteria": "相关性判断标准",
  "max_tokens": 1500,
  "temperature": 0.1
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `system_prompt` | String | 系统级提示词，定义 LLM 的角色和行为准则 |
| `user_prompt_template` | String | 用户提示词模板，包含 `{title}`、`{account_name}`、`{content}`、`{relevance_criteria}` 四个占位符 |
| `relevance_criteria` | String | 相关性判断标准，会被注入到 `user_prompt_template` 中 |
| `max_tokens` | Integer | LLM 响应的最大 token 数 |
| `temperature` | Float | 生成随机性（0.1 = 高度确定性，适合 JSON 输出） |

#### 占位符

| 占位符 | 运行时替换为 |
|---|---|
| `{title}` | 文章标题 |
| `{account_name}` | 来源公众号名称 |
| `{content}` | 文章内容（截取 80%） |
| `{relevance_criteria}` | `relevance_criteria` 字段的值 |

#### 期望的 LLM 输出格式

LLM 必须返回合法的 JSON 对象，不包含任何 Markdown 标记或额外文字：

```json
{
  "is_relevant": true,
  "relevance_score": 8,
  "event_type": "融资",
  "tags": ["tag1", "tag2"],
  "companies": ["公司1", "公司2"],
  "summary_short": "一句话摘要",
  "summary_long": "详细摘要，3到5句话"
}
```

#### 修改指南

**修改相关性标准：**
编辑 `relevance_criteria` 字段，定义你关心的主题范围。例如：

```json
"relevance_criteria": "文章是否与大模型训练基础设施相关"
```

**修改输出字段：**
若需要 LLM 返回额外字段，需同步修改：
1. `user_prompt_template` 中的 JSON 模板
2. 代码中的解析逻辑（`_classify_article_async` 函数）

**修改系统提示词：**
调整 `system_prompt` 可以改变 LLM 的角色定位和专业领域。

**注意事项：**
- `temperature` 建议保持在 0.1 以下，确保 JSON 输出稳定
- `user_prompt_template` 中的 JSON 模板使用双花括号 `{{` 和 `}}` 转义，因为外层使用 `.format()` 方法
- 所有字符串值中的引号和反斜杠必须正确转义
- 不要使用中文引号（""）或特殊 Unicode 字符

---

### 4.3 digest.json — 每日摘要 Prompt

#### 文件结构

```json
{
  "system_prompt": "系统提示词",
  "user_prompt_template": "用户提示词模板（含占位符）",
  "focus_area": "关注领域",
  "max_tokens": 4000,
  "timeout": 120
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `system_prompt` | String | 系统级提示词，定义编辑角色 |
| `user_prompt_template` | String | 用户提示词模板，包含 `{article_count}`、`{top_count}`、`{focus_area}`、`{articles}` 四个占位符 |
| `focus_area` | String | 关注领域描述，会注入到模板中 |
| `max_tokens` | Integer | LLM 响应的最大 token 数 |
| `timeout` | Integer | 请求超时时间（秒） |

#### 占位符

| 占位符 | 运行时替换为 |
|---|---|
| `{article_count}` | 当日文章总数 |
| `{top_count}` | 选取的最重要文章数（最多 20） |
| `{focus_area}` | `focus_area` 字段的值 |
| `{articles}` | 格式化后的文章列表（标题、链接、来源、摘要） |

#### 期望的 LLM 输出格式

LLM 返回 Markdown 格式的每日摘要：

```markdown
## 概述

今日具身智能领域迎来多项重要进展...（3-5 句话）

## 融资动态

- [文章标题 1](https://...) — 来源公众号
- [文章标题 2](https://...) — 来源公众号

## 技术突破

- [文章标题 3](https://...) — 来源公众号
```

#### 修改指南

**修改关注领域：**
编辑 `focus_area` 字段：

```json
"focus_area": "自动驾驶、机器人、AI 芯片"
```

**修改摘要结构：**
编辑 `user_prompt_template` 中的指令部分，可以改变：
- 概述段落长度要求
- 主题分组的规则
- 文章链接格式
- 其他格式要求

**修改系统提示词：**
调整 `system_prompt` 可以改变 LLM 的编辑风格和关注重点。

**注意事项：**
- `## ` 标题前后必须各空一行（解析主题分组时的关键标记）
- 文章链接必须使用 Markdown 格式 `[标题](URL)`
- 不要使用 HTML 标签
- 所有输入文章必须被列出，不能遗漏
- 每篇文章必须归属到一个主题下

---

## 5. 邮件模板配置指南

### 5.1 模板加载机制

系统通过 `apps/api/app/core/prompt_loader.py` 中的 `load_template()` 函数加载邮件模板。

**加载优先级：**

```
1. apps/api/templates/{name}.html          ← 自定义版本（优先）
2. apps/api/templates/{name}.template.html ← 通用模板（回退）
```

**使用方式：**

1. 复制 `email.template.html` 并重命名为 `email.html`
2. 修改 `email.html` 中的 HTML 内容
3. 模板使用 Python `string.Template` 语法，占位符格式为 `${variable}`

> 自定义的 `.html` 文件不会被 git 跟踪。

### 5.2 模板变量

| 变量 | 来源 | 说明 |
|---|---|---|
| `${digest_date}` | 参数传入 | 摘要日期字符串（如 `2026-04-07`） |
| `${item_count}` | 解析得到 | 文章总数量 |
| `${topic_count}` | 解析得到 | 主题分组数量（从 `## ` 标题数统计） |
| `${source_count}` | 解析得到 | 来源公众号数量（从 `— 来源` 后缀提取） |
| `${content_html}` | 自动生成 | 内容区域的 HTML 表格行（`<tr><td>` 结构） |

> **邮件标题和页脚文字直接写在 HTML 模板中**，不在运行时替换。修改标题或页脚只需编辑 `email.html` 对应位置的文本即可。

### 5.3 内容生成流程

邮件内容从 Markdown 到 HTML 的转换过程：

```
DailyDigest.content_markdown
  │
  ▼
1. 解析 Markdown：
   ├── 提取 ## 主题标题
   ├── 提取文章链接（- [标题](URL) — 来源 格式）
   ├── 统计主题数、文章数、来源数
   │
  ▼
2. 构建 content_html：
   将每个主题和文章链接转换为 <tr><td> 表格行
   主题行带蓝色左边框样式
  │
  ▼
3. 加载模板：load_template("email")
  │
  ▼
4. 替换变量：template.substitute(digest_date, item_count, topic_count, source_count, content_html)
  │
  ▼
5. 输出完整 HTML 邮件（标题和页脚文字已在模板中硬编码）
```

### 5.4 修改指南

**修改邮件标题和页脚：**

邮件标题和页脚文字直接写在 `email.html` 模板中，无需修改 Python 代码。

**修改 HTML 结构：**

1. 复制 `email.template.html` 为 `email.html`
2. 编辑 HTML 结构（CSS 样式、布局等）
3. 确保保留 `${digest_date}`、`${item_count}`、`${topic_count}`、`${source_count}`、`${content_html}` 五个占位符
4. `content_html` 变量会插入到模板中对应位置，其内容为 `<tr><td>...</td></tr>` 格式的表格行

**添加新变量：**

1. 在模板中添加 `${new_variable}` 占位符
2. 在 `_build_html_digest()` 的 `template.substitute()` 调用中添加对应键值对

---

## 6. 推送系统详解

### 6.1 两套推送系统对比

系统存在两套并行的推送配置：

| 特性 | 旧版（直接配置） | 统一通知渠道 |
|---|---|---|
| 模型 | `EmailConfig` / `FeishuWebhook` | `NotificationChannel` |
| 支持渠道 | 仅邮件和飞书 | 7 种（飞书/企微/钉钉/Slack/Discord/自定义/邮件） |
| 配置方式 | 专用字段 | `config_json` 灵活配置 |
| API 路径 | `/api/email-configs` / `/api/feishu-webhooks` | `/api/notification-channels` |
| 推荐使用 | 维护兼容 | 新功能优先使用 |

### 6.2 飞书推送

#### 配置字段

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `webhook_url` | String | 必填 | 飞书群机器人完整 Webhook URL |
| `message_title` | String | `"每日摘要"` | 消息卡片标题 |
| `include_source_links` | Boolean | `true` | 是否包含来源链接 |
| `extra_headers_json` | JSON | `{}` | 额外 HTTP 请求头 |
| `sign_secret` | String | 可选 | 签名验证密钥（仅统一渠道支持） |

#### 消息格式（Interactive Card）

飞书推送使用交互式卡片格式：

```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": { "tag": "plain_text", "content": "每日摘要" },
      "template": "blue"
    },
    "elements": [
      {
        "tag": "markdown",
        "content": "**📅 日期**: 2026-04-07  |  **📊 文章数**: 52 篇\n\n---"
      },
      {
        "tag": "markdown",
        "content": "<转换后的 Markdown 内容>"
      }
    ]
  }
}
```

#### Markdown 转换规则

飞书卡片的 Markdown 不支持 `#` 标题，系统自动转换：

| 原始 Markdown | 转换后 |
|---|---|
| `# 文本` | `\n**文本**` |
| `## 文本` | `\n**文本**` |
| `### 文本` | `**文本**` |
| `- [标题](URL) — 来源` | 保持不变 |

同时会移除摘要开头的元信息块（标题、日期、文章数、分隔线），因为这些信息已在卡片头部展示。

#### 签名验证

若配置了 `sign_secret`，请求体会额外包含签名：

```json
{
  "timestamp": "1712476800",
  "sign": "<sha256_hex(timestamp + '\n' + sign_secret)>"
}
```

### 6.3 邮件推送

#### SMTP 配置字段

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `smtp_host` | String | 必填 | SMTP 服务器地址 |
| `smtp_port` | Integer | `587` | SMTP 端口 |
| `use_tls` | Boolean | `true` | 是否使用 STARTTLS |
| `sender_email` | String | 必填 | 发件人邮箱 |
| `sender_name` | String | `"每日摘要"` | 发件人显示名称 |
| `sender_password` | Text | 必填 | SMTP 密码（**Fernet 加密存储**） |
| `recipients_json` | JSON | `[]` | 收件人列表 |
| `cc_recipients` | JSON | `[]` | 抄送列表（仅统一渠道） |
| `template` | String | `"email"` | 邮件模板名称 |

#### 密码加密机制

- 使用 Fernet 对称加密算法
- 密钥派生：`ENCRYPTION_KEY` → SHA-256 → Base64 → Fernet Key
- 加密后的值以 `gAAAA` 开头
- 解密时若失败，会尝试使用原始值（向后兼容）

#### 邮件构建流程

```
1. 解密 SMTP 密码
  │
  ▼
2. 从 DailyDigest 获取 content_markdown
  │
  ▼
3. _build_html_digest()：
   ├── 解析 Markdown 提取结构
   ├── 构建 content_html
   ├── 加载邮件模板
   └── 替换模板变量
  │
  ▼
4. 创建 MIMEMultipart("alternative") 邮件
   ├── Subject: "每日摘要 - {digest_date}"
   ├── From: sender_name <sender_email>
   └── To: 所有收件人
  │
  ▼
5. SMTP 连接：
   ├── 连接 smtp_host:smtp_port
   ├── 可选 starttls()
   ├── 登录 sender_email / 解密后的密码
   └── 发送邮件
```

### 6.4 支持的 7 种渠道类型

| 类型 | config_json 关键字段 | 说明 |
|---|---|---|
| `feishu` | `webhook_url`, `message_title`, `sign_secret` | 飞书群机器人 |
| `wechat_work` | `webhook_url` | 企业微信群机器人 |
| `dingtalk` | `webhook_url`, `sign_secret` | 钉钉群机器人 |
| `slack` | `webhook_url` | Slack Incoming Webhook |
| `discord` | `webhook_url` | Discord Webhook |
| `custom_webhook` | `url`, `method`, `headers`, `body_template` | 完全自定义 |
| `email` | `smtp_host`, `smtp_port`, `sender_email`, `sender_password`, `recipients_json`, `cc_recipients`, `template` | 邮件 |

### 6.5 API 端点

#### 统一通知渠道

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/notification-channels` | 列出所有渠道 |
| `POST` | `/api/notification-channels` | 创建渠道 |
| `PATCH` | `/api/notification-channels/{id}` | 更新渠道 |
| `DELETE` | `/api/notification-channels/{id}` | 删除渠道 |
| `POST` | `/api/notification-channels/test` | 测试渠道（发送示例内容） |
| `POST` | `/api/notification-channels/digests/{digest_id}/send` | 发送指定摘要到多个渠道 |

发送摘要请求体：
```json
{ "channel_ids": ["id1", "id2"] }
```

#### 旧版飞书 Webhook

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/feishu-webhooks` | 列出所有 Webhook |
| `POST` | `/api/feishu-webhooks` | 创建 Webhook |
| `PATCH` | `/api/feishu-webhooks/{id}` | 更新 Webhook |
| `DELETE` | `/api/feishu-webhooks/{id}` | 删除 Webhook |
| `POST` | `/api/feishu-webhooks/send-digest` | 发送摘要到指定 Webhook |

发送摘要请求体：
```json
{ "webhook_id": "...", "digest_id": "..." }
```

#### 旧版邮件配置

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/email-configs` | 列出所有配置 |
| `POST` | `/api/email-configs` | 创建配置 |
| `PATCH` | `/api/email-configs/{id}` | 更新配置 |
| `DELETE` | `/api/email-configs/{id}` | 删除配置 |
| `POST` | `/api/email-configs/send-digest` | 发送摘要到指定配置 |

发送摘要请求体：
```json
{ "config_id": "...", "digest_id": "..." }
```

#### 摘要内容 API

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/content/digests` | 列出所有摘要 |
| `GET` | `/api/content/digests/{id}` | 获取单个摘要 |
| `POST` | `/api/content/digests/generate` | 生成新摘要 |
| `POST` | `/api/content/digests/{id}/send-test` | 发送测试摘要 |

### 6.6 推送数据流

```
DailyDigest (status="published")
  │
  ▼
手动 API 调用：
POST /api/notification-channels/digests/{id}/send
  │
  ▼
notification_service.send_to_channel()
  │
  ├── channel_type = "feishu" → _send_feishu()
  │   └── HTTP POST 到飞书 Webhook
  │
  ├── channel_type = "email" → _send_email()
  │   └── SMTP 发送邮件
  │
  └── 其他类型 → 对应处理函数
  │
  ▼
DailyDigest.status = "sent"
DailyDigest.sent_at = now
```

### 6.7 send_on_digest_generated 标志

`FeishuWebhook`、`EmailConfig` 和 `NotificationChannel` 模型均包含 `send_on_digest_generated` 布尔字段（默认 `false`）。

> **重要：此标志当前未被使用。** 摘要生成流程完成后，不会自动检查此标志并触发推送。推送只能通过手动 API 调用触发。该字段是为未来自动推送功能预留的设计。
