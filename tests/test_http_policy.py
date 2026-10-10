"""deweloperuch_mcp.http_policy: one response policy for recon/ and the package's client.

probe's and the scanner's tests check the policy end to end (limiter pauses, STOP exit
codes); these pin the pure functions the package's HTTP client will call directly.
"""

import math

import pytest

from deweloperuch_mcp import http_policy
from deweloperuch_mcp.http_policy import (
    body_length,
    content_type,
    is_challenge,
    is_html,
    pause_seconds,
    stop_reason,
)

CHALLENGE_HTML = (
    b"<!DOCTYPE html><html><head><title>Just a moment...</title></head>"
    b"<body><script>window._cf_chl_opt={cType:'managed'};</script></body></html>"
)


def test_agreed_limits_and_pauses() -> None:
    assert http_policy.MAX_BODY_BYTES == 32 * 1024 * 1024
    assert http_policy.PAUSE_AFTER_429 == 60.0
    assert http_policy.PAUSE_AFTER_5XX == 30.0
    assert set(http_policy.STOP_STATUSES) == {401, 403, 429}
    assert set(http_policy.PAUSE_5XX_STATUSES) == {502, 503, 504}


@pytest.mark.parametrize(
    ("status", "retry_after", "pause"),
    [
        (429, None, 60.0),  # missing or unreadable Retry-After
        (429, 0.0, 60.0),
        (429, 5.0, 60.0),
        (429, 120.0, 120.0),
        (429, math.inf, math.inf),  # Slot.defer caps it and records the cap
        (502, None, 30.0),
        (503, 45.0, 45.0),
        (504, 0.0, 0.0),  # the service allows a retry now
        (200, 120.0, None),
        (403, 120.0, None),
        (500, 30.0, None),
        (501, None, None),
    ],
)
def test_pause_seconds(status: int, retry_after: float | None, pause: float | None) -> None:
    assert pause_seconds(status, retry_after) == pause


@pytest.mark.parametrize(
    ("status", "headers", "body", "reason"),
    [
        (401, {}, b"", "HTTP 401 (brak autoryzacji)"),
        (403, {}, b"", "HTTP 403 (odmowa dostępu)"),
        (429, {}, b"", "HTTP 429 (limit zapytań)"),
        (200, {"cf-mitigated": "challenge"}, b"{}", "HTTP 200, challenge Cloudflare (captcha/WAF)"),
        (
            403,
            {"content-type": "text/html"},
            CHALLENGE_HTML,
            "HTTP 403 (odmowa dostępu), challenge Cloudflare (captcha/WAF)",
        ),
        (503, {}, CHALLENGE_HTML, "HTTP 503, challenge Cloudflare (captcha/WAF)"),
        (200, {"content-type": "application/json"}, b"{}", None),
        (404, {}, b"not found", None),
        (503, {}, b"maintenance", None),
    ],
)
def test_stop_reason(status: int, headers: dict[str, str], body: bytes, reason: str | None) -> None:
    assert stop_reason(status, headers, body) == reason


@pytest.mark.parametrize(
    "marker",
    [
        "window._cf_chl_opt={}",
        '<div id="cf-browser-verification">',
        '<input name="cf_captcha_kind" value="h">',
        "<title>Just a moment...</title>",
        "<title>Attention Required! | Cloudflare</title>",
    ],
)
def test_each_challenge_marker_in_html(marker: str) -> None:
    html = f"<!DOCTYPE html><html><body>{marker}</body></html>".encode()

    assert is_challenge({"content-type": "text/html"}, html)
    assert is_challenge({}, html)  # recognised as HTML without a content type


def test_markers_count_only_in_html() -> None:
    js = b'var t="<title>Just a moment...</title>";'

    assert not is_challenge({"content-type": "application/javascript"}, js)


def test_turnstile_on_an_app_page_is_not_a_challenge() -> None:
    html = (
        b"<!DOCTYPE html><html><head><title>Mapa</title>"
        b'<script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>'
        b'<script src="/cdn-cgi/challenge-platform/scripts/jsd/main.js"></script></head></html>'
    )

    assert not is_challenge({"content-type": "text/html; charset=utf-8"}, html)


@pytest.mark.parametrize(
    ("headers", "body", "expected"),
    [
        ({"content-type": "text/html; charset=utf-8"}, b"", True),
        ({"content-type": "application/xhtml+xml"}, b"", True),
        ({}, b"  \n<!DOCTYPE html><html>", True),
        ({}, b"<HTML><body>", True),
        ({"content-type": "text/x-component"}, b'0:{"b":"x"}', False),
        ({"content-type": "application/javascript"}, b"(self.webpackChunk=[])", False),
    ],
)
def test_is_html(headers: dict[str, str], body: bytes, expected: bool) -> None:
    assert is_html(headers, body) is expected


def test_content_type_is_lowercase_without_parameters() -> None:
    assert content_type({"content-type": " Text/HTML ; charset=UTF-8"}) == "text/html"
    assert content_type({}) == ""


@pytest.mark.parametrize(
    ("status", "headers", "length"),
    [
        (200, {"content-length": "10"}, "10"),
        (404, {"content-length": "3"}, "3"),
        (200, {"content-length": "10", "transfer-encoding": "chunked"}, None),
        (101, {"content-length": "10"}, None),
        (204, {"content-length": "10"}, None),
        (304, {"content-length": "10"}, None),
        (200, {}, None),
    ],
)
def test_body_length(status: int, headers: dict[str, str], length: str | None) -> None:
    assert body_length(status, headers) == length
