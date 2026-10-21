from __future__ import annotations

from email.utils import parsedate_to_datetime

from research_council.schemas.models import utcnow


def retry_after_seconds(value: str | None, maximum: float = 60) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            seconds = (date - utcnow()).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
    return min(maximum, max(0, seconds))
