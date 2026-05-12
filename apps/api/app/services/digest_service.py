import re
from datetime import datetime, timedelta, timezone

import httpx

from app.core.security import decrypt_api_key
from app.core.prompt_loader import load_prompt
from app.services import event_service

_DIGEST_THEME_TAG_RE = re.compile(r"<!--\s*events:\s*([a-zA-Z0-9,\-\s]+)\s*-->")

_SECTION_CATEGORIES = (
    ("embodied_data", ("数据集", "训练数据", "数据采集", "数据云", "数据标注", "数据基础设施")),
    ("world_model", ("世界模型", "world model", "空间理解")),
    ("embodied_other", ("人形机器人", "具身机器人", "具身智能", "embodied", "具身AI", "机器人")),
)

_SECTION_CATEGORY_ORDER = {
    "embodied_data": 0,
    "world_model": 1,
    "embodied_other": 2,
    "other": 3,
}

_DIGEST_EVENT_SUMMARY_LIMIT = 320


def _ensure_tz(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _fix_markdown_headings(text: str) -> str:
    lines = text.split("\n")
    fixed = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("##"):
            if i > 0 and fixed and fixed[-1].strip() != "":
                fixed.append("")
            fixed.append(stripped)
            if i < len(lines) - 1 and lines[i + 1].strip() != "":
                fixed.append("")
        else:
            fixed.append(line)
    return "\n".join(fixed)


def _sanitize_digest_content(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"https?://[^\s)>]+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _digest_category_name(event: dict) -> str:
    return event.get("event_type") or "其他"


def _group_digest_events_by_category(events: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for event_index, event in enumerate(events):
        category = _digest_category_name(event)
        entry = grouped.setdefault(
            category,
            {
                "name": category,
                "events": [],
            },
        )
        entry["events"].append({**event, "_digest_event_index": event_index})
    return list(grouped.values())


def _digest_publish_time_sort_value(value) -> float:
    dt = _ensure_tz(value)
    if dt is None:
        return 0.0
    return dt.timestamp()


def _render_digest_category_links(category: dict) -> list[str]:
    candidates: list[dict] = []
    for event in category["events"]:
        for article in (event.get("representative_articles") or [])[:3]:
            title = article.get("title")
            url = article.get("article_url")
            if not title or not url:
                continue
            candidates.append(
                {
                    "title": title,
                    "url": url,
                    "source": article.get("account_name") or "未知来源",
                    "importance": event.get("importance") or 0,
                    "publish_sort": _digest_publish_time_sort_value(article.get("publish_time")),
                    "event_index": event.get("_digest_event_index", 0),
                }
            )

    candidates.sort(
        key=lambda item: (
            -(item["importance"] or 0),
            -item["publish_sort"],
            item["event_index"],
        )
    )

    rendered: list[str] = []
    seen_urls: set[str] = set()
    for item in candidates:
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        rendered.append(f"- [{item['title']}]({item['url']}) — {item['source']}")
    return rendered


def _fallback_category_summary(category: dict) -> str:
    item_count = len(category["events"])
    if item_count <= 0:
        return "本分类暂无可展示内容。"
    if item_count == 1:
        return "本分类聚焦 1 个重点事件，下列链接可用于查看完整上下文。"
    return f"本分类共整理 {item_count} 个相关事件，下面汇总代表文章链接供进一步查看。"


def _classify_digest_section(section: dict, theme_pool: dict) -> str:
    text = (section.get("title") or "").lower()

    for category, keywords in _SECTION_CATEGORIES:
        for keyword in keywords:
            if keyword.lower() in text:
                return category

    body_text = (section.get("body") or "").lower()
    data_kw = (
        "数据集", "训练数据", "数据采集", "数据基础设施", "数据编译", "数据范式",
        "数据质量", "训练范式", "仿真数据", "embodied dataset", "data collection",
    )
    for keyword in data_kw:
        if keyword.lower() in body_text:
            return "embodied_data"

    wm_kw = ("世界模型", "world model", "空间理解")
    for keyword in wm_kw:
        if keyword.lower() in body_text:
            return "world_model"

    return "other"


def _sort_digest_sections(sections: list[dict], theme_pool: dict) -> list[dict]:
    def section_key(section):
        category = _classify_digest_section(section, theme_pool)
        return _SECTION_CATEGORY_ORDER.get(category, 3)

    return sorted(sections, key=section_key)


def _build_digest_theme_pool(events: list[dict]) -> dict[str, dict]:
    theme_pool: dict[str, dict] = {}
    for event_index, event in enumerate(events):
        event_id = event.get("id")
        if not event_id:
            continue
        theme_pool[event_id] = {
            **event,
            "_digest_event_index": event_index,
        }
    return theme_pool


def _render_digest_theme_links(theme_events: list[dict]) -> list[str]:
    candidates: list[dict] = []
    for event in theme_events:
        for article in (event.get("representative_articles") or [])[:3]:
            title = article.get("title")
            url = article.get("article_url")
            if not title or not url:
                continue
            candidates.append(
                {
                    "title": title,
                    "url": url,
                    "source": article.get("account_name") or "未知来源",
                    "importance": event.get("importance") or 0,
                    "publish_sort": _digest_publish_time_sort_value(article.get("publish_time")),
                    "event_index": event.get("_digest_event_index", 0),
                }
            )

    candidates.sort(
        key=lambda item: (
            -(item["importance"] or 0),
            -item["publish_sort"],
            item["event_index"],
        )
    )

    rendered: list[str] = []
    seen_urls: set[str] = set()
    for item in candidates:
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        rendered.append(f"- [{item['title']}]({item['url']}) — {item['source']}")
    return rendered


def _fallback_theme_summary(theme_events: list[dict]) -> str:
    item_count = len(theme_events)
    if item_count <= 0:
        return "暂无可展示内容。"
    if item_count == 1:
        return "这里补充 1 个未被主题归纳的重点事件，附上相关文章供进一步查看。"
    return f"这里补充 {item_count} 个未被主题归纳的重点事件，附上相关文章供进一步查看。"


def _parse_digest_theme_sections(content: str) -> tuple[list[str], list[dict]]:
    lines = content.splitlines()
    intro_lines: list[str] = []
    sections: list[dict] = []
    current_section: dict | None = None

    def flush_current():
        nonlocal current_section
        if current_section is None:
            return
        body = "\n".join(current_section["lines"]).strip()
        raw_event_ids = current_section.pop("raw_event_ids", [])
        event_ids: list[str] = []
        seen_ids: set[str] = set()
        for event_id in raw_event_ids:
            if event_id and event_id not in seen_ids:
                seen_ids.add(event_id)
                event_ids.append(event_id)
        sections.append(
            {
                "title": current_section["title"],
                "body": body,
                "event_ids": event_ids,
            }
        )
        current_section = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            flush_current()
            current_section = {
                "title": stripped[3:].strip(),
                "lines": [],
                "raw_event_ids": [],
            }
            continue

        matches = _DIGEST_THEME_TAG_RE.findall(line)
        if matches:
            if current_section is not None:
                for match in matches:
                    current_section["raw_event_ids"].extend([part.strip() for part in match.split(",") if part.strip()])
            continue

        if current_section is None:
            intro_lines.append(line)
        else:
            current_section["lines"].append(line)

    flush_current()
    intro = "\n".join(intro_lines).strip()
    return ([intro] if intro else []), sections


def _inject_digest_theme_links(content: str, events: list[dict]) -> str:
    intro_parts, sections = _parse_digest_theme_sections(content)
    theme_pool = _build_digest_theme_pool(events)
    sections = _sort_digest_sections(sections, theme_pool)
    assigned_event_ids: set[str] = set()
    output: list[str] = [part for part in intro_parts if part]

    for section in sections:
        theme_events: list[dict] = []
        for event_id in section["event_ids"]:
            event = theme_pool.get(event_id)
            if not event:
                continue
            theme_events.append(event)
            assigned_event_ids.add(event_id)

        if output and output[-1].strip():
            output.append("")
        output.append(f"## {section['title']}")
        output.append("")
        if section["body"]:
            output.append(section["body"])
        links = _render_digest_theme_links(theme_events)
        if links:
            output.append("")
            output.extend(links)
        output.append("")

    other_section = next((s for s in sections if s["title"] == "其他重点动态"), None)

    missing_events = [event for event_id, event in theme_pool.items() if event_id not in assigned_event_ids]
    if missing_events and not other_section:
        if output and output[-1].strip():
            output.append("")
        output.append("## 其他重点动态")
        output.append("")
        output.append(_fallback_theme_summary(missing_events))
        links = _render_digest_theme_links(missing_events)
        if links:
            output.append("")
            output.extend(links)
        output.append("")

    return "\n".join(output).strip()


def _call_llm_sync(provider, system_prompt: str, user_prompt: str, timeout: int | None = None) -> dict:
    import time
    api_key = decrypt_api_key(provider.api_key_encrypted)
    url = provider.base_url.rstrip("/") + "/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider.extra_headers_json:
        headers.update(provider.extra_headers_json)

    payload = {
        "model": provider.default_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 4000,
    }

    effective_timeout = timeout or (provider.request_timeout * 3)

    for attempt in range(provider.max_retries):
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=effective_timeout)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"success": True, "content": content, "usage": data.get("usage", {})}
        except Exception as e:
            if attempt == provider.max_retries - 1:
                return {"success": False, "error": str(e)}
            time.sleep(2 ** attempt)

    return {"success": False, "error": "Max retries exceeded"}


def generate_digest_content(events: list[dict], provider, digest_date: datetime | None = None) -> str:
    if not events:
        return "# 每日摘要\n\n今日暂无事件。"

    beijing_tz = timezone(timedelta(hours=8))
    now_beijing = digest_date or datetime.now(beijing_tz)
    header = f"# 每日摘要\n\n**日期**: {now_beijing.strftime('%Y-%m-%d')}\n\n"
    header += f"**共 {len(events)} 个事件**\n\n---\n\n"

    if provider:
        try:
            selected_articles = event_service.select_digest_articles(events, max_articles=30)
            event_summaries = []
            event_theme_pool = _build_digest_theme_pool(events)
            for index, event in enumerate(events, 1):
                participants = "、".join(entity["name"] for entity in event.get("entities", [])[:4]) or "未识别主体"
                event_summary = (event.get("summary_long") or event.get("summary_short") or "暂无摘要").strip()
                latest_article_time = event.get("selection_latest_article_time") or event.get("latest_article_time")
                representative_titles = "；".join(
                    article["title"]
                    for article in event.get("representative_articles", [])[:3]
                    if article.get("title")
                ) or "无"
                event_summaries.append(
                    f"{index}. 事件ID: {event['id']}\n"
                    f"   - 标题: {event['title']}\n"
                    f"   - 当前事件分类: {_digest_category_name(event)}\n"
                    f"   - 参与方: {participants}\n"
                    f"   - 事件摘要: {event_summary[:_DIGEST_EVENT_SUMMARY_LIMIT]}\n"
                    f"   - 最新相关文章时间: {latest_article_time.isoformat() if latest_article_time else '未知'}\n"
                    f"   - 关联文章数: {event.get('article_count', 0)}\n"
                    f"   - 代表文章标题: {representative_titles}"
                )

            article_summaries = []
            for i, article in enumerate(selected_articles, 1):
                event_id = article.get("event_id")
                event = event_theme_pool.get(event_id, {})
                article_summaries.append(
                    f"{i}. [事件ID: {event_id}] {article['title']}\n"
                    f"   - 当前事件分类: {_digest_category_name(event)}\n"
                    f"   - 所属事件: {article['event_title']}\n"
                    f"   - 来源: {article['account_name']}\n"
                    f"   - 发布时间: {article['publish_time'].isoformat() if article.get('publish_time') else '未知'}\n"
                    f"   - 内容摘要: {article['content_text']}"
                )

            prompt_cfg = load_prompt("digest")
            events_text = "\n\n".join(event_summaries)
            articles_text = "\n\n".join(article_summaries) if article_summaries else "无额外文章材料。"
            user_prompt = prompt_cfg["user_prompt_template"].format(
                event_count=len(events),
                article_count=len(selected_articles),
                focus_area=prompt_cfg.get("focus_area", "科技领域"),
                events=events_text,
                articles=articles_text,
            )
            system_prompt = prompt_cfg.get("system_prompt", "")
            timeout = prompt_cfg.get("timeout", 120)

            result = _call_llm_sync(
                provider=provider,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                timeout=timeout,
            )

            if result.get("success"):
                raw = result["content"]
                content = _sanitize_digest_content(raw)
                content = _fix_markdown_headings(content)
                content = _inject_digest_theme_links(content, events)
                content = header + content
                footer = f"\n\n---\n\n*摘要由 AI 自动生成，使用模型: {provider.default_model}*"
                return content + footer
        except Exception:
            pass

    content = header
    by_type = {}
    for event in events:
        by_type.setdefault(event.get("event_type") or "其他", []).append(event)

    content += "## 今日概览\n\n"
    content += f"共识别 **{len(events)}** 个聚合事件。\n\n"

    for event_type, items in by_type.items():
        content += f"## {event_type}\n\n"
        category = {"name": event_type, "events": [{**event, "_digest_event_index": index} for index, event in enumerate(items)]}
        content += _fallback_category_summary(category) + "\n\n"
        links = _render_digest_category_links(category)
        if links:
            content += "\n".join(links) + "\n"
        content += "\n"

    return content
