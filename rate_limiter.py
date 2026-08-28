"""
Rate limiter — Redis sliding window counter.

Two limiters:

1. rate_limit(max_requests, window_seconds)
   - General purpose, used on /shorten/ and similar endpoints
   - Keyed by user_id (authenticated) or IP (unauthenticated)

2. register_rate_limit()
   - Specific to /auth/register
   - Window: 3 hours
   - Threshold: 10 new accounts
   - Key: IP + hashed User-Agent (catches same device even if IP rotates slightly)
   - Logs a WARNING when limit is hit so you have an audit trail
"""

import hashlib
import logging

from fastapi import HTTPException, Request, status
from worker_config import r  # string-mode Redis connection

logger = logging.getLogger(__name__)


# ── General purpose rate limiter ──────────────────────────────────────────────

def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    """
    Returns a FastAPI dependency that enforces a sliding window rate limit.

    - Authenticated users  → keyed by user_id
    - Unauthenticated      → keyed by IP
    - Returns 429 + Retry-After header when limit is exceeded
    """
    def dependency(request: Request):
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            key = f"rate:user:{user_id}"
        else:
            forwarded_for = request.headers.get("X-Forwarded-For")
            ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host
            key = f"rate:ip:{ip}"

        count = r.incr(key)
        if count == 1:
            r.expire(key, window_seconds)

        if count > max_requests:
            ttl = r.ttl(key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {ttl} seconds.",
                headers={"Retry-After": str(ttl)},
            )

    return dependency


# ── Registration-specific rate limiter ────────────────────────────────────────

REGISTER_LIMIT   = 10           # max new accounts allowed per window
REGISTER_WINDOW  = 3 * 60 * 60  # 3 hours in seconds


def register_rate_limit(request: Request):
    """
    FastAPI dependency for POST /auth/register.

    Allows up to 10 new account creations from the same IP or device
    within a 3-hour rolling window. Beyond that, the IP is flagged and
    blocked until the window expires.

    Key strategy:
        - Primary key  → IP address
        - Secondary key → IP + SHA-256(User-Agent)  (catches same device on rotating IP)
    Both counters are checked; whichever is over the threshold blocks the request.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host

    ua_string = request.headers.get("user-agent", "")
    ua_hash = hashlib.sha256(ua_string.encode()).hexdigest()[:16]  # short fingerprint

    ip_key      = f"register:ip:{ip}"
    device_key  = f"register:device:{ip}:{ua_hash}"

    def _check_and_increment(key: str) -> int:
        count = r.incr(key)
        if count == 1:
            r.expire(key, REGISTER_WINDOW)
        return count

    ip_count     = _check_and_increment(ip_key)
    device_count = _check_and_increment(device_key)

    # Flag if either counter exceeds the threshold
    if ip_count > REGISTER_LIMIT or device_count > REGISTER_LIMIT:
        ttl = max(r.ttl(ip_key), r.ttl(device_key))
        logger.warning(
            "REGISTRATION FLAGGED | ip=%s ua_hash=%s "
            "ip_count=%d device_count=%d | blocked for %ds",
            ip, ua_hash, ip_count, device_count, ttl,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many accounts created from this device or IP. "
                f"Try again in {ttl // 3600}h {(ttl % 3600) // 60}m."
            ),
            headers={"Retry-After": str(ttl)},
        )
