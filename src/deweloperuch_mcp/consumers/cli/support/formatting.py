"""The text ``deweloperuch`` prints for people (Polish): numbers (digit groups, decimal
comma), amounts and units, statuses; capability-agnostic (D17). What a command prints is
its presenter's (``consumers/cli/presenters``)."""

_STATUSES = {"active": "aktywna", "archived": "archiwalna"}


def per_m2_unit(currency: str) -> str:
    """``PLN/m²``; without a currency no unit at all (not ``/m²``)."""
    return f"{currency}/m²" if currency else ""


def cell_text(value: float | None) -> str:
    """A value of a statistics table: up to 2 decimals; ``–`` for a period without data."""
    return "–" if value is None else number_text(value, 2)


def status_text(status: str) -> str:
    return _STATUSES.get(status, status)


def count_text(value: int | None) -> str:
    return "?" if value is None else number_text(value)


def amount_text(value: float | None, unit: str, decimals: int = 0, *, signed: bool = False) -> str:
    number = "?" if value is None else number_text(value, decimals, signed=signed)
    return f"{number} {unit}".rstrip()


def number_text(value: float, decimals: int = 0, *, signed: bool = False) -> str:
    """``1234567.5`` -> ``1 234 567,5``: Polish digit groups and decimal comma, no trailing
    zeros; ``signed`` adds ``+`` to positive numbers. Zero is ``0``, never ``-0``/``+0``."""
    text = f"{value:{'+' if signed else ''},.{decimals}f}"
    if decimals:
        text = text.rstrip("0").rstrip(".")
    if text.lstrip("+-") == "0":  # -0.001 rounds to "-0"
        return "0"
    return text.replace(",", " ").replace(".", ",")
