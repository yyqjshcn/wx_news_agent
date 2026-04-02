import httpx
import re
import logging
from typing import Optional
from app.models.feishu_webhook import FeishuWebhook
from app.core.security import decrypt_api_key

logger = logging.getLogger(__name__)

FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/"


async def send_digest_to_feishu(
    webhook: FeishuWebhook,
    content_markdown: str,
    digest_date: str,
    item_count: int,
) -> dict:
    """Send a daily digest to a Feishu group bot webhook using rich text card."""
    try:
        feishu_content = _convert_markdown_to_feishu(content_markdown)

        card_content = _build_feishu_card(
            title=webhook.message_title,
            content=feishu_content,
            digest_date=digest_date,
            item_count=item_count,
            include_links=webhook.include_source_links,
        )

        payload = {
            "msg_type": "interactive",
            "card": card_content,
        }

        headers = {"Content-Type": "application/json"}
        if webhook.extra_headers_json:
            headers.update(webhook.extra_headers_json)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                webhook.webhook_url,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 0:
                return {"success": True, "message": "Digest sent to Feishu"}
            else:
                return {"success": False, "error": f"Feishu API error: {data.get('msg', 'unknown')}"}
    except Exception as e:
        logger.error(f"Failed to send digest to Feishu: {e}")
        return {"success": False, "error": str(e)}


def _convert_markdown_to_feishu(text: str) -> str:
    """Convert standard markdown to Feishu card markdown compatible format.

    Feishu card markdown only supports: **bold**, *italic*, ~~strikethrough~~,
    [link](url), `inline_code`, and lists. It does NOT support # headings.
    """
    lines = text.split("\n")
    result = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("### "):
            heading_text = stripped[4:]
            result.append(f"**{heading_text}**")
        elif stripped.startswith("## "):
            heading_text = stripped[3:]
            result.append(f"\n**{heading_text}**")
        elif stripped.startswith("# "):
            heading_text = stripped[2:]
            result.append(f"\n**{heading_text}**")
        elif stripped.startswith("---"):
            result.append("---")
        elif stripped.startswith("- [") and "](" in stripped:
            match = re.match(r"- \[(.+?)\]\((.+?)\)\s*(.*)", stripped)
            if match:
                title, url, suffix = match.groups()
                if suffix:
                    result.append(f"- [{title}]({url}) {suffix}")
                else:
                    result.append(f"- [{title}]({url})")
            else:
                result.append(stripped)
        else:
            result.append(line)

    return "\n".join(result)


def _build_feishu_card(
    title: str,
    content: str,
    digest_date: str,
    item_count: int,
    include_links: bool = True,
) -> dict:
    """Build a Feishu interactive card from converted markdown content."""
    elements = []

    elements.append({
        "tag": "markdown",
        "content": f"**📅 日期**: {digest_date}\n\n**📊 文章数**: {item_count} 篇\n\n---",
    })

    elements.append({
        "tag": "markdown",
        "content": content,
    })

    card = {
        "header": {
            "title": {
                "tag": "plain_text",
                "content": title,
            },
            "template": "blue",
        },
        "elements": elements,
    }

    return card
