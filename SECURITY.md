# Security policy

Please do not open a public issue for a security problem. Report it privately to the maintainers through the repository's private vulnerability reporting (on GitHub: Security, then Report a vulnerability), or contact the repository owner directly.

This project is a read-only client: it holds no credentials and writes only to its cache directory (`${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp`). The issues most likely to matter are a way to make the client send write requests, to bypass its request limiter or STOP lock, or to read or write files outside that directory.
