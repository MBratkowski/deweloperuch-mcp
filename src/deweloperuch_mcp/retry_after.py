"""Parse the HTTP ``Retry-After`` header (stdlib only).

Shared by ``recon/`` scripts (through ``recon/config.py``) and the package's HTTP
client, so it must import only the standard library: recon loads it without
installing the package.
"""

import re
from datetime import UTC
from email.utils import parsedate_to_datetime

# RFC 9110 delay-seconds is 1*DIGIT; a fraction is tolerated rather than ignored.
_SECONDS = re.compile(r"[0-9]+(?:\.[0-9]+)?")


def parse_retry_after(value: str | None, now: float) -> float | None:
    """Seconds to wait according to ``Retry-After``, or ``None`` if the value is unusable.

    ``value`` is delay-seconds (``"120"``) or an HTTP date
    (``"Wed, 21 Oct 2015 07:28:00 GMT"``, also the obsolete RFC 850 and asctime forms).
    ``now`` is the current wall clock (``time.time()``), needed for dates.

    Missing, empty, negative and unparseable values give ``None``. Digits beyond the
    float range give ``math.inf``: the caller caps it (``Slot.defer`` records its
    maximum) instead of treating it as no delay. A date in the past gives ``0.0``: the
    service allows a retry right away. A date without a zone (asctime, ``-0000``) is
    taken as UTC, as HTTP dates always are.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if _SECONDS.fullmatch(text):
        return float(text)  # digits only: never NaN or negative, inf when too long
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, when.timestamp() - now)
