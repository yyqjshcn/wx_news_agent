import re
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.sql import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import RawArticle
from app.models.event import ArticleEvent, CuratedEvent, Event, EventEntity


_MIN_DATETIME_UTC = datetime.min.replace(tzinfo=timezone.utc)
_DIGEST_EVENT_SUMMARY_LIMIT = 320
_DIGEST_ARTICLE_CONTENT_LIMIT = 480


def normalize_entity_name(name: str | None) -> str:
    if not name:
        return ""
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "", name.strip().lower())
    return normalized


def _normalize_signature(text: str | None) -> str:
    if not text:
        return ""
    normalized = re.sub(r"\s+", "", text.strip().lower())
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "", normalized)
    return normalized[:48]


def _event_window_days(event_type: str | None) -> int:
    if not event_type:
        return 7

    normalized = event_type.lower()
    if normalized in {"融资", "发布", "产品发布", "交付", "funding", "product_launch", "delivery"}:
        return 7
    if normalized in {"合作", "并购", "会议", "展会", "partnership", "conference"}:
        return 14
    if normalized in {"研究", "research"}:
        return 30
    return 10


def _coerce_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            if len(text) == 10:
                return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def _guess_event_title(event_type: str | None, participants: list[dict], fallback: str | None) -> str:
    names = [p["name"] for p in participants if p.get("name")]
    subject = "、".join(names[:2]) if names else "未命名主体"
    if fallback:
        return fallback.strip()[:160]
    if event_type:
        return f"{subject}{event_type}"
    return f"{subject}相关动态"


def _parse_participants(raw_participants, fallback_companies: list[str] | None = None) -> list[dict]:
    participants: list[dict] = []
    fallback_companies = fallback_companies or []
    source = raw_participants if isinstance(raw_participants, list) else fallback_companies

    for item in source:
        if isinstance(item, str):
            name = item.strip()
            if not name:
                continue
            participants.append(
                {
                    "entity_type": "company",
                    "name": name,
                    "normalized_name": normalize_entity_name(name),
                    "role": "participant",
                }
            )
        elif isinstance(item, dict):
            name = (item.get("name") or item.get("company_name") or "").strip()
            if not name:
                continue
            participants.append(
                {
                    "entity_type": item.get("entity_type") or "company",
                    "name": name,
                    "normalized_name": item.get("normalized_name") or normalize_entity_name(name),
                    "role": item.get("role") or "participant",
                }
            )

    deduped: list[dict] = []
    seen = set()
    for participant in participants:
        key = (
            participant["entity_type"],
            participant["normalized_name"],
            participant["role"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(participant)
    return deduped


def build_candidate_events(article: RawArticle, payload: dict | None) -> list[dict]:
    payload = payload or {}
    candidates = payload.get("events")
    built: list[dict] = []

    if isinstance(candidates, list) and candidates:
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            event_type = candidate.get("event_type") or payload.get("event_type")
            participants = _parse_participants(
                candidate.get("participants"),
                fallback_companies=candidate.get("companies") or payload.get("companies") or article.companies_json or [],
            )
            if not event_type and not participants:
                continue
            built.append(
                {
                    "event_type": event_type,
                    "title_hint": candidate.get("title_hint") or candidate.get("title") or article.title,
                    "participants": participants,
                    "summary_short": candidate.get("summary_short") or payload.get("summary_short") or article.summary_short,
                    "event_date": _coerce_datetime(candidate.get("event_date")) or article.publish_time,
                    "confidence": candidate.get("confidence"),
                }
            )

    if built:
        return built

    event_type = payload.get("event_type") or payload.get("primary_event_type") or article.primary_event_type
    companies = payload.get("companies") or article.companies_json or []
    participants = _parse_participants(None, fallback_companies=companies)
    if event_type or participants:
        built.append(
            {
                "event_type": event_type,
                "title_hint": article.title,
                "participants": participants,
                "summary_short": payload.get("summary_short") or article.summary_short,
                "event_date": _coerce_datetime(payload.get("event_date")) or article.publish_time,
                "confidence": payload.get("relevance_score"),
            }
        )
    return built


async def _get_entities_for_events(db: AsyncSession, event_ids: list[str]) -> dict[str, list[EventEntity]]:
    if not event_ids:
        return {}
    result = await db.execute(
        select(EventEntity)
        .where(EventEntity.event_id.in_(event_ids))
        .order_by(EventEntity.created_at.asc())
    )
    entities_by_event: dict[str, list[EventEntity]] = defaultdict(list)
    for entity in result.scalars().all():
        entities_by_event[entity.event_id].append(entity)
    return entities_by_event


async def _get_articles_for_events(db: AsyncSession, event_ids: list[str]) -> dict[str, list[RawArticle]]:
    if not event_ids:
        return {}
    result = await db.execute(
        select(ArticleEvent, RawArticle)
        .join(RawArticle, RawArticle.id == ArticleEvent.article_id)
        .where(ArticleEvent.event_id.in_(event_ids))
        .order_by(RawArticle.publish_time.desc(), RawArticle.created_at.desc())
    )
    articles_by_event: dict[str, list[RawArticle]] = defaultdict(list)
    for link, article in result.all():
        articles_by_event[link.event_id].append(article)
    return articles_by_event


def _serialize_article_summary(article: RawArticle) -> dict:
    return {
        "id": article.id,
        "title": article.title,
        "article_url": article.article_url,
        "account_name": article.account_name,
        "publish_time": article.publish_time,
        "summary_short": article.summary_short,
        "primary_event_type": article.primary_event_type,
    }


def _article_datetime(article: RawArticle) -> datetime | None:
    return _coerce_datetime(article.publish_time or article.created_at)


def _clip_text(text: str | None, limit: int) -> str:
    if not text:
        return ""
    value = text.strip()
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 0)].rstrip() + "…"


def _matches_window(
    dt: datetime | None,
    *,
    window_start: datetime | None,
    window_end: datetime | None,
    window_end_inclusive: bool = True,
) -> bool:
    dt = _coerce_datetime(dt)
    if dt is None or window_start is None or window_end is None:
        return False
    if dt < window_start:
        return False
    if window_end_inclusive:
        return dt <= window_end
    return dt < window_end


def _build_digest_article_payload(
    article: RawArticle,
    *,
    event_id: str,
    event_title: str,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    window_end_inclusive: bool = True,
) -> dict:
    published_at = _article_datetime(article)
    summary_long = (article.summary_long or "").strip()
    summary_short = (article.summary_short or "").strip()
    content_text = summary_long or summary_short or (article.title or "").strip()
    return {
        "id": article.id,
        "event_id": event_id,
        "event_title": event_title,
        "title": article.title,
        "article_url": article.article_url,
        "account_name": article.account_name,
        "publish_time": published_at,
        "summary_long": summary_long,
        "summary_short": summary_short,
        "content_text": _clip_text(content_text, _DIGEST_ARTICLE_CONTENT_LIMIT),
        "has_summary_long": bool(summary_long),
        "is_relevant": bool(article.is_relevant),
        "relevance_score": float(article.relevance_score or 0),
        "in_window": _matches_window(
            published_at,
            window_start=window_start,
            window_end=window_end,
            window_end_inclusive=window_end_inclusive,
        ),
    }


def _digest_article_sort_key(article: dict) -> tuple:
    published_at = _coerce_datetime(article.get("publish_time")) or _MIN_DATETIME_UTC
    return (
        1 if article.get("in_window") else 0,
        1 if article.get("is_relevant") else 0,
        1 if article.get("has_summary_long") else 0,
        published_at,
        float(article.get("relevance_score") or 0),
    )


def select_digest_articles(events: list[dict], max_articles: int = 30) -> list[dict]:
    ranked_by_event: list[tuple[int, str, str, list[dict]]] = []
    selected_ids: set[str] = set()
    selected: list[dict] = []

    for event_index, event in enumerate(events):
        digest_articles = event.get("digest_articles") or []
        if not digest_articles:
            ranked_by_event.append((event_index, event["id"], event["title"], []))
            continue

        ranked = sorted(digest_articles, key=_digest_article_sort_key, reverse=True)
        relevant_ranked = [article for article in ranked if article.get("is_relevant")]
        if relevant_ranked:
            ranked = relevant_ranked + [article for article in ranked if not article.get("is_relevant")]
        ranked_by_event.append((event_index, event["id"], event["title"], ranked))

    for _, event_id, event_title, ranked in ranked_by_event:
        if len(selected) >= max_articles:
            break
        if not ranked:
            continue
        top_article = ranked[0]
        if top_article["id"] in selected_ids:
            continue
        selected_ids.add(top_article["id"])
        selected.append({**top_article, "event_id": event_id, "event_title": event_title})

    remaining: list[tuple[int, dict]] = []
    for event_index, event_id, event_title, ranked in ranked_by_event:
        for article in ranked:
            if article["id"] in selected_ids:
                continue
            remaining.append((event_index, {**article, "event_id": event_id, "event_title": event_title}))

    remaining.sort(key=lambda item: _digest_article_sort_key(item[1]), reverse=True)
    for _, article in remaining:
        if len(selected) >= max_articles:
            break
        if article["id"] in selected_ids:
            continue
        selected_ids.add(article["id"])
        selected.append(article)

    return selected


async def _select_recent_relevant_events(
    db: AsyncSession,
    *,
    window_start: datetime,
    window_end: datetime,
    window_end_inclusive: bool,
) -> tuple[list[Event], dict[str, datetime]]:
    publish_filters = [
        RawArticle.publish_time.is_not(None),
        RawArticle.publish_time >= window_start,
    ]
    if window_end_inclusive:
        publish_filters.append(RawArticle.publish_time <= window_end)
    else:
        publish_filters.append(RawArticle.publish_time < window_end)

    result = await db.execute(
        select(Event, RawArticle)
        .join(ArticleEvent, ArticleEvent.event_id == Event.id)
        .join(RawArticle, RawArticle.id == ArticleEvent.article_id)
        .where(
            Event.status == "active",
            RawArticle.is_relevant == True,
            *publish_filters,
        )
        .order_by(RawArticle.publish_time.desc(), Event.importance.desc(), Event.updated_at.desc())
    )

    grouped: dict[str, dict] = {}
    for event, article in result.all():
        article_time = _article_datetime(article)
        if article_time is None:
            continue
        entry = grouped.setdefault(
            event.id,
            {
                "event": event,
                "latest_article_time": article_time,
            },
        )
        if article_time > entry["latest_article_time"]:
            entry["latest_article_time"] = article_time

    ordered = sorted(
        grouped.values(),
        key=lambda item: (
            item["latest_article_time"],
            item["event"].importance or 0,
            _coerce_datetime(item["event"].updated_at) or _MIN_DATETIME_UTC,
        ),
        reverse=True,
    )
    return [item["event"] for item in ordered], {
        item["event"].id: item["latest_article_time"] for item in ordered
    }


async def _select_fallback_digest_events(
    db: AsyncSession,
    *,
    limit: int,
) -> list[Event]:
    result = await db.execute(
        select(Event)
        .where(Event.status == "active")
        .order_by(
            Event.included_in_digest.desc(),
            Event.importance.desc(),
            func.coalesce(Event.event_date_end, Event.updated_at).desc(),
        )
        .limit(limit)
    )
    return result.scalars().all()


async def _serialize_digest_events(
    db: AsyncSession,
    events: list[Event],
    *,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    window_end_inclusive: bool = True,
    latest_matching_article_time: dict[str, datetime] | None = None,
) -> list[dict]:
    event_ids = [event.id for event in events]
    entities_by_event = await _get_entities_for_events(db, event_ids)
    articles_by_event = await _get_articles_for_events(db, event_ids)

    payloads: list[dict] = []
    for event in events:
        article_models = articles_by_event.get(event.id, [])
        payload = _event_response_payload(
            event,
            entities_by_event.get(event.id, []),
            article_models,
            include_related_articles=True,
        )
        payload["selection_latest_article_time"] = (
            latest_matching_article_time or {}
        ).get(event.id)
        payload["digest_articles"] = [
            _build_digest_article_payload(
                article,
                event_id=event.id,
                event_title=event.title,
                window_start=window_start,
                window_end=window_end,
                window_end_inclusive=window_end_inclusive,
            )
            for article in article_models
        ]
        payloads.append(payload)
    return payloads


def _serialize_entity(entity: EventEntity) -> dict:
    return {
        "id": entity.id,
        "entity_type": entity.entity_type,
        "name": entity.name,
        "normalized_name": entity.normalized_name,
        "role": entity.role,
    }


def _event_response_payload(event: Event, entities: list[EventEntity], articles: list[RawArticle], include_related_articles: bool) -> dict:
    latest_article_time = None
    if articles:
        article_dates = [
            _coerce_datetime(a.publish_time or a.created_at)
            for a in articles
            if (a.publish_time or a.created_at)
        ]
        article_dates = [article_date for article_date in article_dates if article_date is not None]
        if article_dates:
            latest_article_time = max(article_dates)

    payload = {
        "id": event.id,
        "title": event.title,
        "event_type": event.event_type,
        "status": event.status,
        "importance": event.importance,
        "summary_short": event.summary_short,
        "summary_long": event.summary_long,
        "analyst_note": event.analyst_note,
        "included_in_digest": event.included_in_digest,
        "created_by_strategy": event.created_by_strategy,
        "event_date_start": event.event_date_start,
        "event_date_end": event.event_date_end,
        "article_count": len(articles),
        "latest_article_time": latest_article_time,
        "entities": [_serialize_entity(entity) for entity in entities],
        "representative_articles": [_serialize_article_summary(article) for article in articles[:3]],
        "related_articles": [_serialize_article_summary(article) for article in articles] if include_related_articles else [],
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }
    return payload


async def serialize_events(db: AsyncSession, events: list[Event], include_related_articles: bool = False) -> list[dict]:
    event_ids = [event.id for event in events]
    entities_by_event = await _get_entities_for_events(db, event_ids)
    articles_by_event = await _get_articles_for_events(db, event_ids)
    return [
        _event_response_payload(
            event,
            entities_by_event.get(event.id, []),
            articles_by_event.get(event.id, []),
            include_related_articles=include_related_articles,
        )
        for event in events
    ]


def _apply_event_filters(
    query_stmt: Select,
    *,
    event_type: str | None = None,
    status: str | None = None,
    included_in_digest: bool | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    query: str | None = None,
) -> Select:
    if event_type:
        query_stmt = query_stmt.where(Event.event_type == event_type)
    if status:
        query_stmt = query_stmt.where(Event.status == status)
    if included_in_digest is not None:
        query_stmt = query_stmt.where(Event.included_in_digest == included_in_digest)
    if start_date:
        query_stmt = query_stmt.where(or_(Event.event_date_end.is_(None), Event.event_date_end >= start_date))
    if end_date:
        query_stmt = query_stmt.where(or_(Event.event_date_start.is_(None), Event.event_date_start <= end_date))
    if query and query.strip():
        pattern = f"%{query.strip()}%"
        query_stmt = query_stmt.outerjoin(EventEntity, EventEntity.event_id == Event.id).where(
            or_(
                Event.title.ilike(pattern),
                Event.summary_short.ilike(pattern),
                Event.summary_long.ilike(pattern),
                Event.analyst_note.ilike(pattern),
                EventEntity.name.ilike(pattern),
                EventEntity.normalized_name.ilike(pattern),
            )
        )
    return query_stmt


async def list_events(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    event_type: str | None = None,
    status: str | None = None,
    included_in_digest: bool | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    query: str | None = None,
) -> list[dict]:
    query_stmt = _apply_event_filters(
        select(Event).distinct(),
        event_type=event_type,
        status=status,
        included_in_digest=included_in_digest,
        start_date=start_date,
        end_date=end_date,
        query=query,
    )
    query_stmt = query_stmt.order_by(
        func.coalesce(Event.event_date_end, Event.event_date_start, Event.updated_at).desc()
    ).offset(skip).limit(limit)
    result = await db.execute(query_stmt)
    events = result.scalars().all()
    return await serialize_events(db, events)


async def count_events(
    db: AsyncSession,
    event_type: str | None = None,
    status: str | None = None,
    included_in_digest: bool | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    query: str | None = None,
) -> int:
    query_stmt = _apply_event_filters(
        select(func.count(func.distinct(Event.id))),
        event_type=event_type,
        status=status,
        included_in_digest=included_in_digest,
        start_date=start_date,
        end_date=end_date,
        query=query,
    )
    result = await db.execute(query_stmt)
    return result.scalar() or 0


async def get_event(db: AsyncSession, event_id: str, include_related_articles: bool = True) -> dict | None:
    event = await db.get(Event, event_id)
    if not event:
        return None
    serialized = await serialize_events(db, [event], include_related_articles=include_related_articles)
    return serialized[0]


async def create_event(db: AsyncSession, data: dict) -> Event:
    entities = data.pop("entities", None) or []
    title = data.get("title") or _guess_event_title(data.get("event_type"), entities, None)
    event = Event(
        id=str(uuid.uuid4()),
        title=title,
        status=data.get("status") or "active",
        importance=data.get("importance") or 3,
        summary_short=data.get("summary_short"),
        summary_long=data.get("summary_long"),
        analyst_note=data.get("analyst_note"),
        included_in_digest=bool(data.get("included_in_digest", False)),
        created_by_strategy=data.get("created_by_strategy") or "manual",
        event_type=data.get("event_type"),
        event_date_start=data.get("event_date_start"),
        event_date_end=data.get("event_date_end") or data.get("event_date_start"),
    )
    db.add(event)
    await db.flush()
    await _sync_event_entities(db, event.id, entities, replace=True)
    return event


async def update_event(db: AsyncSession, event_id: str, data: dict) -> Event | None:
    event = await db.get(Event, event_id)
    if not event:
        return None
    entities = data.pop("entities", None)
    for key, value in data.items():
        if value is not None:
            setattr(event, key, value)
    event.updated_at = datetime.now(timezone.utc)
    if entities is not None:
        await _sync_event_entities(db, event.id, entities, replace=True)
    db.add(event)
    await db.flush()
    return event


async def delete_event(db: AsyncSession, event_id: str) -> bool:
    event = await db.get(Event, event_id)
    if not event:
        return False
    article_links = await db.execute(select(ArticleEvent).where(ArticleEvent.event_id == event_id))
    for link in article_links.scalars().all():
        await db.delete(link)
    entities = await db.execute(select(EventEntity).where(EventEntity.event_id == event_id))
    for entity in entities.scalars().all():
        await db.delete(entity)
    await db.delete(event)
    await db.flush()
    return True


async def _sync_event_entities(db: AsyncSession, event_id: str, entities: list[dict], replace: bool = False):
    seen = set()
    if replace:
        result = await db.execute(select(EventEntity).where(EventEntity.event_id == event_id))
        for entity in result.scalars().all():
            await db.delete(entity)
    else:
        existing = await db.execute(select(EventEntity).where(EventEntity.event_id == event_id))
        for entity in existing.scalars().all():
            seen.add(
                (
                    entity.entity_type or "company",
                    entity.normalized_name or normalize_entity_name(entity.name),
                    entity.role or "participant",
                )
            )
    for raw in entities or []:
        name = raw.get("name")
        if not name:
            continue
        normalized_name = raw.get("normalized_name") or normalize_entity_name(name)
        key = (raw.get("entity_type") or "company", normalized_name, raw.get("role") or "participant")
        if key in seen:
            continue
        seen.add(key)
        db.add(
            EventEntity(
                id=str(uuid.uuid4()),
                event_id=event_id,
                entity_type=raw.get("entity_type") or "company",
                name=name,
                normalized_name=normalized_name,
                role=raw.get("role") or "participant",
            )
        )
    await db.flush()


async def get_events_for_articles(db: AsyncSession, article_ids: list[str]) -> dict[str, list[dict]]:
    if not article_ids:
        return {}

    result = await db.execute(
        select(ArticleEvent, Event)
        .join(Event, Event.id == ArticleEvent.event_id)
        .where(ArticleEvent.article_id.in_(article_ids))
        .order_by(Event.importance.desc(), Event.updated_at.desc())
    )

    article_to_events: dict[str, list[Event]] = defaultdict(list)
    event_ids: list[str] = []
    for link, event in result.all():
        article_to_events[link.article_id].append(event)
        event_ids.append(event.id)

    entities_by_event = await _get_entities_for_events(db, list(set(event_ids)))
    serialized: dict[str, list[dict]] = {}
    for article_id, events in article_to_events.items():
        serialized[article_id] = [
            {
                "id": event.id,
                "title": event.title,
                "event_type": event.event_type,
                "importance": event.importance,
                "included_in_digest": event.included_in_digest,
                "event_date_start": event.event_date_start,
                "event_date_end": event.event_date_end,
                "entity_names": [entity.name for entity in entities_by_event.get(event.id, [])],
            }
            for event in events
        ]
    return serialized


async def _create_article_link(
    db: AsyncSession,
    article_id: str,
    event_id: str,
    role: str = "source",
    confidence: float | None = None,
    is_primary: bool = False,
):
    existing = await db.execute(
        select(ArticleEvent).where(
            ArticleEvent.article_id == article_id,
            ArticleEvent.event_id == event_id,
        )
    )
    link = existing.scalar_one_or_none()
    if link:
        if confidence is not None:
            link.confidence = confidence
        link.role = role or link.role
        link.is_primary = link.is_primary or is_primary
        db.add(link)
        await db.flush()
        return link

    link = ArticleEvent(
        id=str(uuid.uuid4()),
        article_id=article_id,
        event_id=event_id,
        role=role,
        confidence=confidence,
        is_primary=is_primary,
    )
    db.add(link)
    await db.flush()
    return link


async def _update_event_rollup(event: Event, article: RawArticle, candidate: dict):
    event.importance = max(event.importance or 0, int(round(article.relevance_score or 3)))
    if candidate.get("summary_short") and not event.summary_short:
        event.summary_short = candidate["summary_short"]
    if article.summary_long and not event.summary_long:
        event.summary_long = article.summary_long
    event.updated_at = datetime.now(timezone.utc)
    event_date = _coerce_datetime(candidate.get("event_date") or article.publish_time)
    current_start = _coerce_datetime(event.event_date_start)
    current_end = _coerce_datetime(event.event_date_end)
    if event_date:
        if not current_start or event_date < current_start:
            event.event_date_start = event_date
        if not current_end or event_date > current_end:
            event.event_date_end = event_date


async def _find_matching_event(
    db: AsyncSession,
    article: RawArticle,
    candidate: dict,
) -> Event | None:
    event_type = candidate.get("event_type")
    event_date = _coerce_datetime(candidate.get("event_date") or article.publish_time or article.created_at)
    if event_date is None:
        event_date = datetime.now(timezone.utc)
    window_days = _event_window_days(event_type)
    window_start = event_date - timedelta(days=window_days)
    window_end = event_date + timedelta(days=window_days)
    signature = _normalize_signature(candidate.get("title_hint") or article.title)
    participant_names = {
        participant.get("normalized_name") or normalize_entity_name(participant.get("name"))
        for participant in candidate.get("participants", [])
        if participant.get("name")
    }

    query = select(Event).where(Event.status == "active")
    if event_type:
        query = query.where(Event.event_type == event_type)
    query = query.where(
        or_(Event.event_date_start.is_(None), Event.event_date_start <= window_end),
        or_(Event.event_date_end.is_(None), Event.event_date_end >= window_start),
    ).order_by(Event.updated_at.desc()).limit(30)

    result = await db.execute(query)
    candidates = result.scalars().all()
    if not candidates:
        return None

    entities_by_event = await _get_entities_for_events(db, [event.id for event in candidates])
    for event in candidates:
        existing_names = {
            entity.normalized_name or normalize_entity_name(entity.name)
            for entity in entities_by_event.get(event.id, [])
            if entity.name
        }
        title_signature = _normalize_signature(event.title)
        participant_overlap = bool(participant_names and participant_names & existing_names)
        signature_overlap = bool(signature and title_signature and (signature in title_signature or title_signature in signature))
        no_participants = not participant_names and not existing_names
        if (participant_overlap and (signature_overlap or len(participant_names) == 1)) or (no_participants and signature_overlap):
            return event
    return None


async def _create_event_from_candidate(db: AsyncSession, article: RawArticle, candidate: dict) -> Event:
    event_date = _coerce_datetime(candidate.get("event_date") or article.publish_time or article.created_at)
    event = Event(
        id=str(uuid.uuid4()),
        title=_guess_event_title(candidate.get("event_type"), candidate.get("participants", []), candidate.get("title_hint") or article.title),
        event_type=candidate.get("event_type"),
        status="active",
        importance=int(round(article.relevance_score or 3)),
        summary_short=candidate.get("summary_short") or article.summary_short,
        summary_long=article.summary_long,
        included_in_digest=False,
        created_by_strategy="auto",
        event_date_start=event_date,
        event_date_end=event_date,
    )
    db.add(event)
    await db.flush()
    await _sync_event_entities(db, event.id, candidate.get("participants", []), replace=False)
    return event


async def _cleanup_auto_event_if_orphan(db: AsyncSession, event_id: str):
    event = await db.get(Event, event_id)
    if not event or event.created_by_strategy != "auto":
        return
    result = await db.execute(select(func.count(ArticleEvent.id)).where(ArticleEvent.event_id == event_id))
    count = result.scalar() or 0
    if count:
        return
    entities = await db.execute(select(EventEntity).where(EventEntity.event_id == event_id))
    for entity in entities.scalars().all():
        await db.delete(entity)
    await db.delete(event)
    await db.flush()


async def sync_article_events(db: AsyncSession, article: RawArticle, payload: dict | None) -> list[Event]:
    candidates = build_candidate_events(article, payload)

    existing_result = await db.execute(
        select(ArticleEvent).where(
            ArticleEvent.article_id == article.id,
            ArticleEvent.role == "source",
        )
    )
    existing_links = existing_result.scalars().all()
    orphan_candidates = [link.event_id for link in existing_links]
    for link in existing_links:
        await db.delete(link)
    await db.flush()
    for event_id in orphan_candidates:
        await _cleanup_auto_event_if_orphan(db, event_id)

    synced_events: list[Event] = []
    for idx, candidate in enumerate(candidates):
        event = await _find_matching_event(db, article, candidate)
        if event is None:
            event = await _create_event_from_candidate(db, article, candidate)
        else:
            await _update_event_rollup(event, article, candidate)
            await _sync_event_entities(db, event.id, candidate.get("participants", []), replace=False)
            db.add(event)
            await db.flush()

        await _create_article_link(
            db,
            article_id=article.id,
            event_id=event.id,
            role="source",
            confidence=candidate.get("confidence"),
            is_primary=(idx == 0),
        )
        synced_events.append(event)
    return synced_events


async def attach_article_to_event(
    db: AsyncSession,
    event_id: str,
    article_id: str,
    role: str = "manual",
    confidence: float | None = None,
    is_primary: bool = False,
) -> Event | None:
    event = await db.get(Event, event_id)
    article = await db.get(RawArticle, article_id)
    if not event or not article:
        return None

    await _create_article_link(db, article_id, event_id, role=role, confidence=confidence, is_primary=is_primary)
    await _update_event_rollup(
        event,
        article,
        {
            "event_date": article.publish_time,
            "summary_short": article.summary_short,
            "participants": _parse_participants(None, fallback_companies=article.companies_json or []),
        },
    )
    await _sync_event_entities(
        db,
        event_id,
        _parse_participants(None, fallback_companies=article.companies_json or []),
        replace=False,
    )
    db.add(event)
    await db.flush()
    return event


async def detach_article_from_event(db: AsyncSession, event_id: str, article_id: str) -> bool:
    result = await db.execute(
        select(ArticleEvent).where(
            ArticleEvent.event_id == event_id,
            ArticleEvent.article_id == article_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        return False
    await db.delete(link)
    await db.flush()
    return True


async def merge_events(db: AsyncSession, event_ids: list[str], target_event_id: str | None = None) -> Event | None:
    unique_ids = list(dict.fromkeys([event_id for event_id in event_ids if event_id]))
    if len(unique_ids) < 2:
        return None

    target_id = target_event_id or unique_ids[0]
    target = await db.get(Event, target_id)
    if not target:
        return None

    for source_id in unique_ids:
        if source_id == target.id:
            continue
        source = await db.get(Event, source_id)
        if not source:
            continue

        link_result = await db.execute(select(ArticleEvent).where(ArticleEvent.event_id == source_id))
        for link in link_result.scalars().all():
            await _create_article_link(
                db,
                article_id=link.article_id,
                event_id=target.id,
                role=link.role or "source",
                confidence=link.confidence,
                is_primary=link.is_primary,
            )
            await db.delete(link)

        entities_result = await db.execute(select(EventEntity).where(EventEntity.event_id == source_id))
        entities = entities_result.scalars().all()
        await _sync_event_entities(
            db,
            target.id,
            [
                {
                    "entity_type": entity.entity_type,
                    "name": entity.name,
                    "normalized_name": entity.normalized_name,
                    "role": entity.role,
                }
                for entity in entities
            ],
            replace=False,
        )
        for entity in entities:
            await db.delete(entity)

        target.included_in_digest = target.included_in_digest or source.included_in_digest
        target.importance = max(target.importance or 0, source.importance or 0)
        target.created_by_strategy = "merged"
        if not target.summary_short and source.summary_short:
            target.summary_short = source.summary_short
        if not target.summary_long and source.summary_long:
            target.summary_long = source.summary_long
        source_start = _coerce_datetime(source.event_date_start)
        target_start = _coerce_datetime(target.event_date_start)
        source_end = _coerce_datetime(source.event_date_end)
        target_end = _coerce_datetime(target.event_date_end)
        if source_start and (not target_start or source_start < target_start):
            target.event_date_start = source.event_date_start
        if source_end and (not target_end or source_end > target_end):
            target.event_date_end = source.event_date_end
        await db.delete(source)

    target.updated_at = datetime.now(timezone.utc)
    db.add(target)
    await db.flush()
    return target


async def split_event(
    db: AsyncSession,
    event_id: str,
    article_ids: list[str],
    title: str | None = None,
    event_type: str | None = None,
    included_in_digest: bool | None = None,
) -> Event | None:
    source = await db.get(Event, event_id)
    if not source:
        return None

    selected_ids = list(dict.fromkeys(article_ids))
    if not selected_ids:
        return None

    article_result = await db.execute(
        select(ArticleEvent, RawArticle)
        .join(RawArticle, RawArticle.id == ArticleEvent.article_id)
        .where(
            ArticleEvent.event_id == event_id,
            ArticleEvent.article_id.in_(selected_ids),
        )
    )
    rows = article_result.all()
    if not rows:
        return None

    selected_articles = [article for _, article in rows]
    selected_dates = [
        _coerce_datetime(article.publish_time or article.created_at)
        for article in selected_articles
        if (article.publish_time or article.created_at)
    ]
    selected_dates = [event_date for event_date in selected_dates if event_date is not None]
    participants = _parse_participants(
        None,
        fallback_companies=[company for article in selected_articles for company in (article.companies_json or [])],
    )
    new_event = Event(
        id=str(uuid.uuid4()),
        title=title or f"{source.title}（拆分）",
        event_type=event_type or source.event_type,
        status="active",
        importance=max([source.importance or 0] + [int(round(article.relevance_score or 3)) for article in selected_articles]),
        summary_short=selected_articles[0].summary_short or source.summary_short,
        summary_long=selected_articles[0].summary_long or source.summary_long,
        analyst_note=source.analyst_note,
        included_in_digest=source.included_in_digest if included_in_digest is None else included_in_digest,
        created_by_strategy="manual",
        event_date_start=min(selected_dates) if selected_dates else None,
        event_date_end=max(selected_dates) if selected_dates else None,
    )
    db.add(new_event)
    await db.flush()
    await _sync_event_entities(db, new_event.id, participants, replace=False)

    for link, article in rows:
        await _create_article_link(
            db,
            article_id=article.id,
            event_id=new_event.id,
            role="manual",
            confidence=link.confidence,
            is_primary=link.is_primary,
        )
        await db.delete(link)

    remaining_count = (
        await db.execute(select(func.count(ArticleEvent.id)).where(ArticleEvent.event_id == source.id))
    ).scalar() or 0
    if remaining_count == 0:
        entities = await db.execute(select(EventEntity).where(EventEntity.event_id == source.id))
        for entity in entities.scalars().all():
            await db.delete(entity)
        await db.delete(source)
    else:
        source.updated_at = datetime.now(timezone.utc)
        db.add(source)

    await db.flush()
    return new_event


async def get_digest_candidate_events(
    db: AsyncSession,
    now: datetime | None = None,
    fallback_limit: int = 30,
) -> list[dict]:
    now = _coerce_datetime(now) or datetime.now(timezone.utc)
    window_24h = now - timedelta(hours=24)
    window_48h = now - timedelta(hours=48)

    recent_events, recent_latest_article_time = await _select_recent_relevant_events(
        db,
        window_start=window_24h,
        window_end=now,
        window_end_inclusive=True,
    )
    if recent_events:
        return await _serialize_digest_events(
            db,
            recent_events,
            window_start=window_24h,
            window_end=now,
            window_end_inclusive=True,
            latest_matching_article_time=recent_latest_article_time,
        )

    older_events, older_latest_article_time = await _select_recent_relevant_events(
        db,
        window_start=window_48h,
        window_end=window_24h,
        window_end_inclusive=False,
    )
    if older_events:
        return await _serialize_digest_events(
            db,
            older_events,
            window_start=window_48h,
            window_end=window_24h,
            window_end_inclusive=False,
            latest_matching_article_time=older_latest_article_time,
        )

    fallback_events = await _select_fallback_digest_events(db, limit=fallback_limit)
    if not fallback_events:
        return []
    return await _serialize_digest_events(db, fallback_events)


async def _select_events_by_date_range(
    db: AsyncSession,
    *,
    date_start: datetime,
    date_end: datetime,
) -> list[Event]:
    window_start = _coerce_datetime(date_start)
    window_end = _coerce_datetime(date_end)
    if window_start is None or window_end is None:
        return []

    if window_start > window_end:
        window_start, window_end = window_end, window_start

    result = await db.execute(
        select(Event)
        .distinct()
        .join(ArticleEvent, ArticleEvent.event_id == Event.id)
        .join(RawArticle, RawArticle.id == ArticleEvent.article_id)
        .where(
            Event.status == "active",
            RawArticle.is_relevant == True,
            RawArticle.publish_time >= window_start,
            RawArticle.publish_time <= window_end,
        )
        .order_by(Event.importance.desc(), Event.updated_at.desc())
    )
    return result.scalars().all()


async def _select_events_by_article_ids(
    db: AsyncSession,
    *,
    article_ids: list[str],
) -> list[Event]:
    if not article_ids:
        return []

    result = await db.execute(
        select(Event)
        .distinct()
        .join(ArticleEvent, ArticleEvent.event_id == Event.id)
        .where(
            Event.status == "active",
            ArticleEvent.article_id.in_(article_ids),
        )
        .order_by(Event.importance.desc(), Event.updated_at.desc())
    )
    return result.scalars().all()


async def get_events_by_custom_criteria(
    db: AsyncSession,
    *,
    date_start: datetime | None = None,
    date_end: datetime | None = None,
    article_ids: list[str] | None = None,
) -> list[dict]:
    events: list[Event] = []

    if article_ids:
        events = await _select_events_by_article_ids(db, article_ids=article_ids)
    elif date_start is not None and date_end is not None:
        events = await _select_events_by_date_range(
            db, date_start=date_start, date_end=date_end
        )

    if not events:
        return []

    return await _serialize_digest_events(
        db,
        events,
        window_start=_coerce_datetime(date_start),
        window_end=_coerce_datetime(date_end),
        window_end_inclusive=True,
    )


async def migrate_legacy_curated_events(db: AsyncSession) -> dict:
    curated_result = await db.execute(
        select(CuratedEvent, RawArticle)
        .join(RawArticle, RawArticle.id == CuratedEvent.article_id)
    )
    migrated = 0
    curated_by_article: dict[str, dict] = {}

    for curated, article in curated_result.all():
        entry = curated_by_article.setdefault(
            article.id,
            {
                "article": article,
                "events": [],
                "included_in_digest": False,
                "importance": 0,
            },
        )
        entry["events"].append(
            {
                "event_type": curated.event_type or article.primary_event_type,
                "title_hint": curated.one_line_summary or article.title,
                "participants": [curated.company_name] if curated.company_name else article.companies_json or [],
                "summary_short": curated.one_line_summary or article.summary_short,
                "event_date": curated.event_date or article.publish_time,
                "confidence": curated.importance,
            }
        )
        entry["included_in_digest"] = entry["included_in_digest"] or curated.included_in_digest
        entry["importance"] = max(entry["importance"], curated.importance or 0)

    for entry in curated_by_article.values():
        article = entry["article"]
        events = await sync_article_events(db, article, {"events": entry["events"]})
        for event in events:
            event.included_in_digest = event.included_in_digest or entry["included_in_digest"]
            event.importance = max(event.importance or 0, entry["importance"] or 0)
            db.add(event)
        migrated += len(events)

    article_result = await db.execute(
        select(RawArticle).where(
            RawArticle.status == "classified",
            or_(RawArticle.primary_event_type.is_not(None), RawArticle.companies_json.is_not(None)),
        )
    )
    for article in article_result.scalars().all():
        existing = await db.execute(
            select(func.count(ArticleEvent.id)).where(ArticleEvent.article_id == article.id)
        )
        if (existing.scalar() or 0) > 0:
            continue
        migrated += len(await sync_article_events(db, article, {}))

    return {"migrated_events": migrated}
