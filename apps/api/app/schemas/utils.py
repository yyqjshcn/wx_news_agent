from datetime import datetime, timezone


def ensure_utc(v: datetime | None) -> datetime | None:
    """Ensure a datetime is timezone-aware (UTC). SQLite returns naive datetimes."""
    if v is None:
        return None
    if v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v
