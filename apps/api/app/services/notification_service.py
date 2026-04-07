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
    smtp_host = cfg.get("smtp_host", "")
    smtp_port = cfg.get("smtp_port", 587)
    sender_email = cfg.get("sender_email", "")
    sender_password_encrypted = cfg.get("sender_password", "")
    recipients = cfg.get("recipients", [])
    cc_recipients = cfg.get("cc_recipients", [])
    all_recipients = recipients + cc_recipients

    if not smtp_host:
        raise ValueError("SMTP host is not configured")
    if not sender_email:
        raise ValueError("Sender email is not configured")
    if not all_recipients:
        raise ValueError("No recipients configured")

    # Decrypt password (handle both encrypted and plain text for backward compatibility)
    try:
        sender_password = decrypt_api_key(sender_password_encrypted)
    except Exception:
        # If decryption fails, try using the password as-is (plain text fallback)
        sender_password = sender_password_encrypted

    html_content = _build_html_digest(content, digest_date, item_count, cfg.get("template", "email"))

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"世界模型与具身智能每日新闻摘要 - {digest_date}"
    msg["From"] = f"{cfg.get('sender_name', '每日摘要')} <{sender_email}>"
    msg["To"] = ", ".join(recipients)
    if cc_recipients:
        msg["Cc"] = ", ".join(cc_recipients)
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    server = None
    try:
        if cfg.get("use_tls", True):
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)

        server.login(sender_email, sender_password)
        server.sendmail(sender_email, all_recipients, msg.as_string())
        return {"success": True, "message": f"Sent to {len(recipients)} recipient(s), {len(cc_recipients)} cc(s)"}
    except smtplib.SMTPAuthenticationError as e:
        raise ValueError(f"SMTP authentication failed: {e}")
    except smtplib.SMTPConnectError as e:
        raise ValueError(f"Failed to connect to SMTP server {smtp_host}:{smtp_port}: {e}")
    except smtplib.SMTPException as e:
        raise ValueError(f"SMTP error: {e}")
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass


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


def _build_html_digest(content_markdown: str, digest_date: str, item_count: int, template_name: str = "email") -> str:
    import re
    from app.core.prompt_loader import load_template

    lines = content_markdown.split("\n")

    # Parse content to extract sections and stats
    sections = []  # list of {"title": str, "items": list}
    current_section = {"title": None, "items": [], "intro": ""}
    topic_count = 0
    sources = set()

    skip_header = True
    for line in lines:
        stripped = line.strip()
        if skip_header:
            if stripped.startswith("# ") or stripped.startswith("## "):
                continue
            if stripped.startswith("**日期**") or stripped.startswith("**共") or stripped.startswith("---"):
                continue
            if stripped == "":
                continue
            skip_header = False

        if stripped.startswith("## "):
            if current_section["title"] is not None or current_section["items"] or current_section["intro"].strip():
                sections.append(current_section)
                topic_count += 1
            current_section = {"title": stripped[3:], "items": [], "intro": ""}
        elif stripped.startswith("- [") and "](" in stripped:
            match = re.match(r"- \[(.+?)\]\((.+?)\)\s*(.*)", stripped)
            if match:
                title, url, suffix = match.groups()
                # Extract source from suffix like "— 来源公众号"
                source = ""
                if "—" in suffix:
                    source = suffix.split("—", 1)[1].strip()
                    sources.add(source)
                current_section["items"].append({"title": title, "url": url, "suffix": suffix, "source": source})
        elif stripped and not stripped.startswith("---") and not stripped.startswith("**"):
            if current_section["title"] is None and not current_section["items"]:
                current_section["intro"] += stripped + " "
            elif current_section["title"] is not None and not current_section["items"]:
                current_section["intro"] += stripped + " "

    if current_section["title"] is not None or current_section["items"] or current_section["intro"].strip():
        sections.append(current_section)
        if current_section["title"]:
            topic_count += 1

    # Build content HTML (sections only, not the full page)
    content_parts = []
    for section in sections:
        if section["title"]:
            content_parts.append('<tr><td style="padding: 24px 32px 8px;">')
            content_parts.append(f'<div style="border-left: 3px solid #1E40AF; padding-left: 12px;">')
            content_parts.append(f'<h2 style="font-size: 17px; font-weight: 700; color: #1a1a1a; margin: 0 0 4px;">{section["title"]}</h2>')
            if section["intro"].strip():
                content_parts.append(f'<p style="font-size: 13px; color: #666; margin: 4px 0 0; line-height: 1.5;">{section["intro"].strip()}</p>')
            content_parts.append('</div>')
            content_parts.append('</td></tr>')
        elif section["intro"].strip():
            content_parts.append('<tr><td style="padding: 24px 32px 8px;">')
            content_parts.append(f'<p style="font-size: 14px; color: #444; line-height: 1.7; margin: 0;">{section["intro"].strip()}</p>')
            content_parts.append('</td></tr>')

        for item in section["items"]:
            content_parts.append('<tr><td style="padding: 6px 32px 6px 44px;">')
            content_parts.append(f'<div style="font-size: 14px; line-height: 1.6;">')
            content_parts.append(f'<span style="color: #1E40AF; margin-right: 6px;">&#8226;</span>')
            content_parts.append(f'<a href="{item["url"]}" style="color: #1a1a1a; text-decoration: underline; font-weight: 600;">{item["title"]}</a>')
            if item["source"]:
                content_parts.append(f'<span style="color: #999; font-size: 12px; margin-left: 6px;">{item["source"]}</span>')
            content_parts.append('</div>')
            content_parts.append('</td></tr>')

    content_html = "\n".join(content_parts)

    # Load email template and substitute variables
    template = load_template(template_name)
    return template.substitute(
        digest_date=digest_date,
        item_count=str(item_count),
        topic_count=str(topic_count),
        source_count=str(len(sources)),
        content_html=content_html,
    )
