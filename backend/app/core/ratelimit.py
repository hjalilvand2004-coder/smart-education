"""محدودسازی نرخ ساده درون‌حافظه‌ای برای مسیرهای حساس (مثل ورود).

در استقرار چندنمونه‌ای باید با Redis پیاده شود؛ اینجا برای MVP است.
"""
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.errors import rate_limited

_BUCKETS: dict[str, deque] = defaultdict(deque)


def rate_limit(scope: str, limit: int, window_seconds: int):
    """Dependency factory: حداکثر limit درخواست در پنجره زمانی برای هر IP."""

    def _dep(request: Request):
        ip = request.client.host if request.client else "unknown"
        key = f"{scope}:{ip}"
        now = time.monotonic()
        bucket = _BUCKETS[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise rate_limited()
        bucket.append(now)

    return _dep
