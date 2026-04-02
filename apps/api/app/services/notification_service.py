"""
Unified notification channel dispatcher.
Routes digest sending to the appropriate channel handler.
"""
import logging
from app.models.notification_channel import NotificationChannel

logger = logging.getLogger(__name__)


async def send_to_channel(channel: NotificationChannel, content_markdown: str, digest_date: str, item_count: int) -> dict:
    """Send digest to a notification channel."""
    dispatchers = {
        "feishu": _send_feishu,
        "wechat_work": _send_wechat_work,
        "dingtalk": _send_dingtalk,
        "slack": _send_slack,
        "discord": _send_discord,
        "custom_webhook": _send_custom_webhook,
        "email": _send_email,
    }

    handler = dispatchers.get(channel.channel_type)
    if not handler:
        return {"success": False, "error": f"Unknown channel type: {channel.channel_type}"}

    try:
        return await handler(channel, content_markdown, digest_date, item_count)
    except Exception as e:
        logger.error(f"Failed to send to channel {channel.alias} ({channel.channel_type}): {e}")
        return {"success": False, "error": str(e)}


async def _send_feishu(channel, content, digest_date, item_count):
    import httpx
    from app.core.security import decrypt_api_key
    import hashlib
    import time

    cfg = channel.config_json
    webhook_url = cfg.get("webhook_url", "")
    message_title = cfg.get("message_title", "每日摘要")
    include_links = cfg.get("include_source_links", True)
    sign_secret = cfg.get("sign_secret", "")

    # Build card content
    card_content = _convert_markdown_to_feishu(content)

    card = {
        "header": {
            "title": {"tag": "plain_text", "content": message_title},
            "template": "blue",
        },
        "elements": [
            {"tag": "markdown", "content": f"**📅 日期**: {digest_date}  |  **📊 文章数**: {item_count} 篇\n\n---"},
            {"tag": "markdown", "content": card_content},
        ],
    }

    payload = {"msg_type": "interactive", "card": card}
    headers = {"Content-Type": "application/json"}

    if sign_secret:
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{sign_secret}"
        signature = hashlib.sha256(string_to_sign.encode()).hexdigest()
        payload["timestamp"] = timestamp
        payload["sign"] = signature

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(webhook_url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0:
            return {"success": True, "message": "Sent to Feishu"}
        return {"success": False, "error": f"Feishu API error: {data.get('msg', 'unknown')}"}


async def _send_wechat_work(channel, content, digest_date, item_count):
    import httpx

    cfg = channel.config_json
    webhook_url = cfg.get("webhook_url", "")

    # Convert markdown to plain text for WeChat Work
    text_content = _markdown_to_plain_text(content)
    header = f"📅 {digest_date} | 📊 {item_count} 篇\n\n"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"# {cfg.get('message_title', '每日摘要')}\n\n{header}{text_content}"
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(webhook_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") == 0:
            return {"success": True, "message": "Sent to WeChat Work"}
        return {"success": False, "error": f"WeChat Work API error: {data.get('errmsg', 'unknown')}"}


async def _send_dingtalk(channel, content, digest_date, item_count):
    import httpx
    import hashlib
    import hmac
    import base64
    import time
    import urllib.parse

    cfg = channel.config_json
    webhook_url = cfg.get("webhook_url", "")
    sign_secret = cfg.get("sign_secret", "")

    final_url = webhook_url
    if sign_secret:
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{sign_secret}"
        hmac_code = hmac.new(
            sign_secret.encode(), string_to_sign.encode(), digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        final_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

    text_content = _markdown_to_plain_text(content)
    header = f"**📅 日期**: {digest_date}  |  **📊 文章数**: {item_count} 篇\n\n---\n\n"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": cfg.get("message_title", "每日摘要"),
            "text": f"# {cfg.get('message_title', '每日摘要')}\n\n{header}{text_content}",
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(final_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") == 0:
            return {"success": True, "message": "Sent to DingTalk"}
        return {"success": False, "error": f"DingTalk API error: {data.get('errmsg', 'unknown')}"}


async def _send_slack(channel, content, digest_date, item_count):
    import httpx

    cfg = channel.config_json
    webhook_url = cfg.get("webhook_url", "")
    channel_name = cfg.get("channel", "")

    text_content = _markdown_to_plain_text(content)
    header = f"📅 {digest_date} | 📊 {item_count} 篇"

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": cfg.get("message_title", "每日摘要")}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{header}*"}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": text_content}},
    ]

    payload = {"blocks": blocks}
    if channel_name:
        payload["channel"] = channel_name

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(webhook_url, json=payload)
        resp.raise_for_status()
        if resp.status_code == 200:
            return {"success": True, "message": "Sent to Slack"}
        return {"success": False, "error": f"Slack API error: {resp.text[:200]}"}


async def _send_discord(channel, content, digest_date, item_count):
    import httpx

    cfg = channel.config_json
    webhook_url = cfg.get("webhook_url", "")

    text_content = _markdown_to_plain_text(content)
    header = f"📅 {digest_date} | 📊 {item_count} 篇"

    payload = {
        "embeds": [{
            "title": cfg.get("message_title", "每日摘要"),
            "description": f"{header}\n\n{text_content}",
            "color": 3447003,
        }]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(webhook_url, json=payload)
        resp.raise_for_status()
        if resp.status_code in (200, 204):
            return {"success": True, "message": "Sent to Discord"}
        return {"success": False, "error": f"Discord API error: {resp.text[:200]}"}


async def _send_custom_webhook(channel, content, digest_date, item_count):
    import httpx

    cfg = channel.config_json
    webhook_url = cfg.get("webhook_url", "")
    method = cfg.get("method", "POST").upper()
    headers = cfg.get("headers_json", {})
    body_template = cfg.get("body_template", '{"content": "{content}"}')

    # Replace placeholders
    body = body_template.replace("{content}", content)
    body = body.replace("{digest_date}", digest_date)
    body = body.replace("{item_count}", str(item_count))
    body = body.replace("{title}", cfg.get("message_title", "每日摘要"))

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(method, webhook_url, headers=headers, content=body)
        resp.raise_for_status()
        return {"success": True, "message": f"Sent to custom webhook ({method} {webhook_url})"}


async def _send_email(channel, content, digest_date, item_count):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from app.core.security import decrypt_api_key

    cfg = channel.config_json
    sender_password = decrypt_api_key(cfg.get("sender_password", ""))
    html_content = _build_html_digest(content, digest_date, item_count)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{cfg.get('message_title', '每日摘要')} - {digest_date}"
    msg["From"] = f"{cfg.get('sender_name', '每日摘要')} <{cfg.get('sender_email', '')}>"
    msg["To"] = ", ".join(cfg.get("recipients", []))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    if cfg.get("use_tls", True):
        server = smtplib.SMTP(cfg.get("smtp_host", ""), cfg.get("smtp_port", 587))
        server.starttls()
    else:
        server = smtplib.SMTP(cfg.get("smtp_host", ""), cfg.get("smtp_port", 587))

    server.login(cfg.get("sender_email", ""), sender_password)
    server.sendmail(cfg.get("sender_email", ""), cfg.get("recipients", []), msg.as_string())
    server.quit()

    return {"success": True, "message": f"Sent to {len(cfg.get('recipients', []))} recipient(s)"}


# --- Helper functions ---

def _convert_markdown_to_feishu(text: str) -> str:
    import re
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            result.append(f"**{stripped[4:]}**")
        elif stripped.startswith("## "):
            result.append(f"\n**{stripped[3:]}**")
        elif stripped.startswith("# "):
            result.append(f"\n**{stripped[2:]}**")
        elif stripped.startswith("---"):
            result.append("---")
        elif stripped.startswith("- [") and "](" in stripped:
            match = re.match(r"- \[(.+?)\]\((.+?)\)\s*(.*)", stripped)
            if match:
                title, url, suffix = match.groups()
                result.append(f"- [{title}]({url}) {suffix}" if suffix else f"- [{title}]({url})")
            else:
                result.append(stripped)
        else:
            result.append(line)
    return "\n".join(result)


def _markdown_to_plain_text(text: str) -> str:
    import re
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    return text


def _build_html_digest(content_markdown: str, digest_date: str, item_count: int) -> str:
    import re
    lines = content_markdown.split("\n")
    parts = []
    parts.append('<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 680px; margin: 0 auto; padding: 20px; color: #1a1a1a;">')
    parts.append(f'<div style="background: #f8f9fa; padding: 16px 20px; border-radius: 8px; margin-bottom: 24px;"><span style="font-size: 14px; color: #666;">📅 日期: {digest_date}</span><span style="margin-left: 20px; font-size: 14px; color: #666;">📊 文章数: {item_count} 篇</span></div>')

    for line in lines:
        stripped = line.strip()
        if not stripped:
            parts.append("<br>")
        elif stripped.startswith("# "):
            parts.append(f'<h1 style="font-size: 22px; margin: 0 0 12px 0;">{stripped[2:]}</h1>')
        elif stripped.startswith("## "):
            parts.append(f'<h2 style="font-size: 17px; margin: 20px 0 8px 0; color: #333;">{stripped[3:]}</h2>')
        elif stripped.startswith("### "):
            parts.append(f'<h3 style="font-size: 15px; margin: 16px 0 6px 0; color: #555;">{stripped[4:]}</h3>')
        elif stripped.startswith("---"):
            parts.append('<hr style="border: none; border-top: 1px solid #e0e0e0; margin: 16px 0;">')
        elif stripped.startswith("- [") and "](" in stripped:
            match = re.match(r"- \[(.+?)\]\((.+?)\)\s*(.*)", stripped)
            if match:
                title, url, suffix = match.groups()
                link = f'<a href="{url}" style="color: #2563eb; text-decoration: none;">{title}</a>'
                parts.append(f'<div style="margin: 4px 0 4px 16px; font-size: 14px;">• {link} {suffix}</div>' if suffix else f'<div style="margin: 4px 0 4px 16px; font-size: 14px;">• {link}</div>')
            else:
                parts.append(f'<div style="margin: 4px 0; font-size: 14px;">{stripped}</div>')
        elif stripped.startswith("**") and stripped.endswith("**"):
            parts.append(f'<p style="font-weight: bold; margin: 8px 0; font-size: 14px;">{stripped[2:-2]}</p>')
        else:
            parts.append(f'<p style="margin: 6px 0; font-size: 14px; line-height: 1.6;">{stripped}</p>')

    parts.append("</div>")
    return "\n".join(parts)
