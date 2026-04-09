import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.models.email_config import EmailConfig
from app.core.security import decrypt_api_key

logger = logging.getLogger(__name__)


def _build_html_digest(content_markdown: str, digest_date: str, item_count: int) -> str:
    """Convert simplified markdown to HTML for email."""
    import re

    lines = content_markdown.split("\n")
    html_parts = []

    html_parts.append(
        f'<div style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; '
        f'max-width: 680px; margin: 0 auto; padding: 20px; color: #1a1a1a;">'
    )

    html_parts.append(
        f'<div style="background: #f8f9fa; padding: 16px 20px; border-radius: 8px; margin-bottom: 24px;">'
        f'<span style="font-size: 14px; color: #666;">📅 日期: {digest_date}</span>'
        f'<span style="margin-left: 20px; font-size: 14px; color: #666;">📊 事件数: {item_count} 个</span>'
        f'</div>'
    )

    for line in lines:
        stripped = line.strip()

        if not stripped:
            html_parts.append("<br>")
            continue

        if stripped.startswith("# "):
            text = stripped[2:]
            html_parts.append(f'<h1 style="font-size: 22px; margin: 0 0 12px 0;">{text}</h1>')
        elif stripped.startswith("## "):
            text = stripped[3:]
            html_parts.append(f'<h2 style="font-size: 17px; margin: 20px 0 8px 0; color: #333;">{text}</h2>')
        elif stripped.startswith("### "):
            text = stripped[4:]
            html_parts.append(f'<h3 style="font-size: 15px; margin: 16px 0 6px 0; color: #555;">{text}</h3>')
        elif stripped.startswith("---"):
            html_parts.append('<hr style="border: none; border-top: 1px solid #e0e0e0; margin: 16px 0;">')
        elif stripped.startswith("- [") and "](" in stripped:
            match = re.match(r"- \[(.+?)\]\((.+?)\)\s*(.*)", stripped)
            if match:
                title, url, suffix = match.groups()
                link_html = f'<a href="{url}" style="color: #2563eb; text-decoration: none;">{title}</a>'
                if suffix:
                    html_parts.append(f'<div style="margin: 4px 0 4px 16px; font-size: 14px;">• {link_html} {suffix}</div>')
                else:
                    html_parts.append(f'<div style="margin: 4px 0 4px 16px; font-size: 14px;">• {link_html}</div>')
            else:
                html_parts.append(f'<div style="margin: 4px 0; font-size: 14px;">{stripped}</div>')
        elif stripped.startswith("**") and stripped.endswith("**"):
            text = stripped[2:-2]
            html_parts.append(f'<p style="font-weight: bold; margin: 8px 0; font-size: 14px;">{text}</p>')
        elif stripped.startswith("*") and stripped.endswith("*"):
            text = stripped[1:-1]
            html_parts.append(f'<p style="font-style: italic; color: #888; margin: 8px 0; font-size: 13px;">{text}</p>')
        else:
            html_parts.append(f'<p style="margin: 6px 0; font-size: 14px; line-height: 1.6;">{stripped}</p>')

    html_parts.append("</div>")
    return "\n".join(html_parts)


async def send_digest_email(
    config: EmailConfig,
    content_markdown: str,
    digest_date: str,
    item_count: int,
) -> dict:
    """Send a daily digest via email."""
    try:
        sender_password = decrypt_api_key(config.sender_password)
        html_content = _build_html_digest(content_markdown, digest_date, item_count)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"每日摘要 - {digest_date}"
        msg["From"] = f"{config.sender_name} <{config.sender_email}>"
        msg["To"] = ", ".join(config.recipients_json)

        msg.attach(MIMEText(html_content, "html", "utf-8"))

        if config.use_tls:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP(config.smtp_host, config.smtp_port)

        server.login(config.sender_email, sender_password)
        server.sendmail(config.sender_email, config.recipients_json, msg.as_string())
        server.quit()

        return {"success": True, "message": f"Digest sent to {len(config.recipients_json)} recipient(s)"}
    except Exception as e:
        logger.error(f"Failed to send digest email: {e}")
        return {"success": False, "error": str(e)}
