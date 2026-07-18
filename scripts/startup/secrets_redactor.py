"""Redact secrets from log strings.

Covers Authorization headers, token=, password=, cookie= and any
secret-like assignment passed via environment. The redactor is
deliberately conservative — when in doubt, it redacts.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable

# Match things that look like credentials. Order matters: longer/more
# specific patterns first.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Authorization: <scheme> <value>...
    re.compile(r"(Authorization\s*:\s*)[^\r\n,;]+", re.IGNORECASE),
    # Cookie: <name>=<value>... (raw cookie strings)
    re.compile(r"(Cookie\s*:\s*)[^\r\n,;]+", re.IGNORECASE),
    # key=value or key="value" with a sensitive key (no quotes allowed in val)
    re.compile(
        r"(?ix)(?P<key>(?:access[_-]?token|api[_-]?key|auth[_-]?token|"
        r"client[_-]?secret|password|secret[_-]?key|token|cookie|"
        r"session[_-]?id))(?P<sep>\s*[:=]\s*)(?P<val>[^\s,;'\"`]+)"
    ),
    # Bearer xxx...
    re.compile(r"(Bearer\s+)[^\s,;]+", re.IGNORECASE),
    # Long hex/base64-looking strings preceded by 'token='
    re.compile(r"(token\s*=\s*)([A-Za-z0-9._\-]{16,})", re.IGNORECASE),
)

_REDACTED = "[REDACTED]"


def redact(text: str) -> str:
    """Return ``text`` with credentials redacted."""
    if not text:
        return text
    out = text
    for pat in _PATTERNS:
        out = pat.sub(lambda m: _replace(m), out)
    return out


def _replace(m: re.Match[str]) -> str:
    groups = m.groupdict()
    if groups.get("key") and groups.get("val"):
        return f"{groups['key']}{groups['sep']}{_REDACTED}"
    if groups.get("key"):
        # No separator captured (rare) — redact whole match
        return f"{_REDACTED}"
    # Patterns without named groups: keep the leading capture (group 1)
    g1 = m.group(1) if m.lastindex and m.lastindex >= 1 else ""
    return f"{g1}{_REDACTED}"


def scrub_env(env: dict | None = None,
              keys: Iterable[str] | None = None) -> dict:
    """Return a dict where any sensitive env value is replaced by [REDACTED]."""
    keys = set(keys or (
        "AUTHORIZATION", "TOKEN", "PASSWORD", "SECRET", "API_KEY",
        "ACCESS_TOKEN", "SESSION_ID", "COOKIE", "MY_SECRET_TOKEN",
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HF_TOKEN",
    ))
    src = env if env is not None else dict(os.environ)
    out = {}
    for k, v in src.items():
        if k.upper() in keys or any(s in k.upper() for s in ("TOKEN", "PASSWORD", "SECRET", "KEY", "COOKIE", "AUTH")):
            out[k] = _REDACTED
        else:
            out[k] = v
    return out


def scrub_dict(d: dict) -> dict:
    """Return a deep copy of d with secret-looking values redacted."""
    out = {}
    for k, v in d.items():
        if isinstance(v, str) and any(s in k.lower() for s in (
            "token", "password", "secret", "auth", "cookie",
        )):
            out[k] = _REDACTED
        elif isinstance(v, dict):
            out[k] = scrub_dict(v)
        else:
            out[k] = v
    return out
