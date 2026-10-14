"""Text of the service made safe for a terminal or a log (D12): escaping, not wording.

Error details (``DeweloperuchError.detail``) may carry text the service sent (a body, a
header); the CLI and the MCP server pass them through ``printable`` before they show or
log them.
"""


def printable(text: str) -> str:
    """``text`` with every non-printable character as an escape, ``repr``-like.

    ``"a\\x1b]0;x\\x07"`` -> ``"a\\\\x1b]0;x\\\\x07"``: no terminal control sequences (OSC,
    CSI), no line breaks, no invisible bidi controls. Printable text, Polish letters
    included, stays as it is.
    """
    return "".join(char if char.isprintable() else _escape(char) for char in text)


def _escape(char: str) -> str:
    code = ord(char)
    if code < 0x100:
        return f"\\x{code:02x}"
    if code < 0x10000:
        return f"\\u{code:04x}"
    return f"\\U{code:08x}"
