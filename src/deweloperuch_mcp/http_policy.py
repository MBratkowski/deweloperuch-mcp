"""What a response from deweloperuch.pl means for the requests after it (stdlib only).

One policy (CLAUDE.md, D2) for the ``recon/`` scripts, which get it through
``recon/config.py``, and for the package's HTTP client:

- ``stop_reason``: 401, 403, 429 and Cloudflare challenges (captcha, WAF) stop the
  whole series of requests; nothing is retried. ``stop_cause`` is what the STOP record of
  the shared limiter keeps of such an answer (``Slot.stop``);
- ``pause_seconds``: how long the shared limiter pauses after a 429 or a 502/503/504;
- ``body_length`` and ``MAX_BODY_BYTES``: whether a declared body length applies and
  how big a body may be (bigger ones are dumps, D5).

Pure functions, no I/O: callers read the body, parse ``Retry-After``
(``deweloperuch_mcp.retry_after``) and record the pause (``Slot.defer``). Header names
are looked up in lowercase: pass a mapping with lowercase keys or a case-insensitive one
(``httpx.Headers``).

Keep this module free of imports outside the standard library: ``recon/`` scripts load
it without installing the package or its dependencies.
"""

from collections.abc import Mapping

MAX_BODY_BYTES = 32 * 1024 * 1024
"""Largest body read from the service; bigger ones are dumps (D5) and are refused."""

PAUSE_AFTER_429 = 60.0
"""Least pause after a 429, whatever ``Retry-After`` says or if it is missing."""

PAUSE_AFTER_5XX = 30.0
"""Pause after a 502/503/504 without a usable ``Retry-After``."""

STOP_STATUSES: Mapping[int, str] = {
    401: "brak autoryzacji",
    403: "odmowa dostępu",
    429: "limit zapytań",
}
"""Statuses that stop the series of requests, with the reason shown to the user."""

CHALLENGE = "challenge"
"""``status`` of the STOP record after a Cloudflare challenge, whatever the HTTP status."""

CHALLENGE_REASON = "challenge Cloudflare (captcha/WAF)"

PAUSE_5XX_STATUSES = frozenset({502, 503, 504})
"""Gateway errors that pause the limiter (``Retry-After`` or ``PAUSE_AFTER_5XX``)."""

# Cloudflare challenge and block pages (besides the `cf-mitigated` header), looked for
# only in HTML. Turnstile itself (challenges.cloudflare.com) and the injected
# /cdn-cgi/challenge-platform script are not markers: the site's own pages embed them.
CHALLENGE_MARKERS = (
    "_cf_chl_opt",
    "cf-browser-verification",
    "cf_captcha_kind",
    "<title>Just a moment...</title>",
    "Attention Required! | Cloudflare",
)


def body_length(status: int, headers: Mapping[str, str]) -> str | None:
    """``Content-Length`` if it describes the body, as http.client reads it (RFC 9112 §6.3).

    Ignored with ``Transfer-Encoding`` (the encoding delimits the body) and for 1xx,
    204 and 304, which have no body whatever the header says.

    The value counts bytes on the wire, before any ``Content-Encoding`` is undone. A
    client that decompresses (httpx does by default) must compare it with the raw byte
    count (``Response.num_bytes_downloaded``), not with the decoded body, or skip the
    comparison.
    """
    if "transfer-encoding" in headers or 100 <= status < 200 or status in (204, 304):
        return None
    return headers.get("content-length")


def content_type(headers: Mapping[str, str]) -> str:
    """The media type, lowercase, without parameters; ``""`` without the header."""
    return headers.get("content-type", "").split(";", 1)[0].strip().lower()


def is_html(headers: Mapping[str, str], body: bytes) -> bool:
    """An HTML page, by its content type or, without a usable one, by its first bytes."""
    if content_type(headers) in ("text/html", "application/xhtml+xml"):
        return True
    # A bounded prefix: lstrip() of a whole body would copy up to MAX_BODY_BYTES.
    return body[:1024].lstrip()[:15].lower().startswith((b"<!doctype html", b"<html"))


def is_challenge(headers: Mapping[str, str], body: bytes) -> bool:
    """Cloudflare answered instead of the application (challenge, captcha, WAF block)."""
    if "cf-mitigated" in headers:
        return True
    if not is_html(headers, body):
        return False
    text = body.decode("utf-8", "replace")
    return any(marker in text for marker in CHALLENGE_MARKERS)


def stop_reason(status: int, headers: Mapping[str, str], body: bytes) -> str | None:
    """Why this response stops the series of requests (``"HTTP 429 (limit zapytań)"``).

    ``None`` when it does not. A challenge stops whatever the status, also on a 200.
    The status is named only when it is a STOP status itself (``"HTTP 403 (odmowa
    dostępu), challenge Cloudflare (captcha/WAF)"``); a challenge on another status is
    just ``CHALLENGE_REASON``: "HTTP 200" next to a STOP reads like a success. Callers
    keep the status in their details.
    """
    challenge = is_challenge(headers, body)
    parts = [f"HTTP {status} ({STOP_STATUSES[status]})"] if status in STOP_STATUSES else []
    if challenge:
        parts.append(CHALLENGE_REASON)
    return ", ".join(parts) or None


def stop_cause(
    status: int, headers: Mapping[str, str], body: bytes
) -> tuple[int | str, str] | None:
    """What the STOP record keeps of this answer: ``(status, reason)``; ``None`` for no STOP.

    A challenge is ``(CHALLENGE, CHALLENGE_REASON)`` whatever the status, so it never
    ends on its own (``Slot.stop``); otherwise the status and its ``STOP_STATUSES`` text.
    Stops exactly when ``stop_reason`` does. Never the target, the headers or the body.
    """
    if is_challenge(headers, body):
        return CHALLENGE, CHALLENGE_REASON
    if status in STOP_STATUSES:
        return status, STOP_STATUSES[status]
    return None


def pause_seconds(status: int, retry_after: float | None) -> float | None:
    """Pause of the shared limiter after a response with ``status``; ``None`` for no pause.

    ``retry_after`` is the parsed ``Retry-After`` (``None`` when missing or unreadable;
    it may be ``math.inf``, which ``Slot.defer`` caps). 429: ``max(Retry-After,
    PAUSE_AFTER_429)``. 502/503/504: ``Retry-After``, or ``PAUSE_AFTER_5XX`` without a
    usable one. Any other status: ``None``.
    """
    if status == 429:
        return max(retry_after or 0.0, PAUSE_AFTER_429)
    if status in PAUSE_5XX_STATUSES:
        return PAUSE_AFTER_5XX if retry_after is None else retry_after
    return None
