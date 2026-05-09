"""
Workflow failure alert service.
Sends detailed failure notifications via a configured webhook URL.
"""
import httpx
import logging
from datetime import datetime, timezone

from app.core.config import get_settings
from app.models.workflow import Workflow, WorkflowRun, TriggerType

logger = logging.getLogger(__name__)

WORKFLOW_TYPE_LABELS = {
    "daily_ingest": "每日采集",
    "midday_refresh": "中午刷新",
    "classify_pending_articles": "文章分类",
    "generate_daily_digest": "生成每日摘要",
    "retry_failed_jobs": "重试失败任务",
    "login_health_check": "登录健康检查",
    "rss_ingest": "RSS 采集",
    "sequential_pipeline": "顺序流水线",
}

TRIGGER_TYPE_LABELS = {
    "scheduled": "定时调度",
    "manual": "手动触发",
    "retry": "重试",
}


async def send_workflow_failure_alert(
    workflow: Workflow,
    run: WorkflowRun,
    error_message: str,
    duration_ms: int | None = None,
) -> bool:
    """Send a failure alert to the configured webhook URL.

    Returns True if the alert was sent successfully, False otherwise.
    Silently skips if no webhook URL is configured.
    """
    settings = get_settings()
    webhook_url = settings.WORKFLOW_FAIL_WEBHOOK_URL

    if not webhook_url or not webhook_url.strip():
        return False

    trigger_label = TRIGGER_TYPE_LABELS.get(
        run.trigger_type.value if hasattr(run.trigger_type, "value") else str(run.trigger_type),
        str(run.trigger_type),
    )
    workflow_label = WORKFLOW_TYPE_LABELS.get(
        workflow.workflow_type.value if hasattr(workflow.workflow_type, "value") else str(workflow.workflow_type),
        workflow.workflow_type,
    )

    failed_at = run.finished_at or datetime.now(timezone.utc)
    if run.started_at:
        duration_ms = duration_ms or int(
            (failed_at - run.started_at).total_seconds() * 1000
        )
    duration_str = format_duration(duration_ms)

    safe_error = sanitize_error(error_message)

    message = (
        f"🚨 **工作流运行失败**\n\n"
        f"• **名称**: {workflow.workflow_name}（{workflow_label}）\n"
        f"• **触发方式**: {trigger_label}\n"
        f"• **失败时间**: {format_datetime(failed_at)}\n"
        f"• **运行时长**: {duration_str}\n"
        f"• **Run ID**: `{run.id}`\n\n"
        f"**错误信息**:\n```\n{safe_error}\n```"
    )

    return await _send_webhook(webhook_url, message)


async def _send_webhook(url: str, message: str) -> bool:
    """Send a markdown message to a webhook URL using multiple payload formats."""
    headers = {"Content-Type": "application/json"}

    # Try common webhook payload formats in parallel
    payloads = [
        {"msg_type": "text", "content": {"text": message}},
        {"msg_type": "interactive", "card": {"header": {"title": {"tag": "plain_text", "content": "🚨 工作流失败告警"}, "template": "red"}, "elements": [{"tag": "markdown", "content": message}]}},
        {"text": message},
        {"content": message},
    ]

    for payload in payloads:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()

                data = resp.json() if resp.text else {}
                if _is_success_response(data):
                    logger.info("Workflow failure alert sent successfully")
                    return True
                logger.warning(f"Webhook sent but returned warning: {data}")
                return True
        except httpx.ConnectError:
            logger.error(f"Failed to connect to webhook URL: {url}")
            return False
        except httpx.HTTPStatusError as e:
            logger.warning(f"Webhook rejected payload with status {e.response.status_code}: {e.response.text[:200]}")
            continue
        except Exception as e:
            logger.error(f"Failed to send workflow failure alert: {e}")
            return False

    return False


def _is_success_response(data: dict) -> bool:
    """Check if a webhook response indicates success across platforms."""
    code = data.get("code")
    if code is not None:
        return code == 0
    errcode = data.get("errcode")
    if errcode is not None:
        return errcode == 0
    return True


def sanitize_error(message: str | None) -> str:
    """Truncate and sanitize error message for display."""
    if not message:
        return "(no error message)"
    msg = str(message).strip()
    if len(msg) > 1500:
        msg = msg[:1500] + "...\n(truncated)"
    return msg


def format_datetime(dt: datetime | None) -> str:
    """Format datetime to readable string in Asia/Shanghai timezone."""
    if dt is None:
        return "(unknown)"
    from datetime import timedelta
    beijing_tz = timezone(timedelta(hours=8))
    dt_bj = dt.astimezone(beijing_tz)
    return dt_bj.strftime("%Y-%m-%d %H:%M:%S CST")


def format_duration(ms: int | None) -> str:
    """Format duration in milliseconds to human-readable string."""
    if ms is None or ms < 0:
        return "(unknown)"
    total_seconds = ms / 1000
    if total_seconds < 60:
        return f"{total_seconds:.1f}秒"
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes}分{seconds:.0f}秒"
