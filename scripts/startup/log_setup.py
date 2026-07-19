"""Logging setup that always scrubs secrets and is safe to call multiple times."""

from __future__ import annotations

import logging
import os
import sys
from logging import Logger
from pathlib import Path

from . import secrets_redactor as _redact


class _SecretFilter(logging.Filter):
    """Filter that runs every record's message through the redactor."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            clean = _redact.redact(msg)
            if clean != msg:
                record.msg = clean
                record.args = ()
        except Exception:
            pass
        return True


_FORMAT = "%(asctime)s %(levelname)-5s [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S%z"


def get_logger(
    name: str = "reproctl.startup", log_file: Path | None = None, level: str | None = None
) -> Logger:
    """Return a logger configured with the secret filter.

    Idempotent: re-calling returns the same logger with filters intact.
    """
    logger = logging.getLogger(name)
    if getattr(logger, "_reproctl_configured", False):
        # Re-attach file handler if a different file is requested
        if log_file is not None:
            _attach_file(logger, log_file)
        if level is not None:
            logger.setLevel(level.upper())
        return logger

    logger.setLevel((level or os.environ.get("REPRO_LOG_LEVEL") or "INFO").upper())
    logger.propagate = False

    fmt = logging.Formatter(_FORMAT, _DATEFMT)

    # Stream handler (stderr)
    sh = logging.StreamHandler(stream=sys.stderr)
    sh.setFormatter(fmt)
    sh.addFilter(_SecretFilter())
    logger.addHandler(sh)

    if log_file is not None:
        _attach_file(logger, log_file)

    logger._reproctl_configured = True  # type: ignore[attr-defined]
    return logger


def _attach_file(logger: Logger, log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(_FORMAT, _DATEFMT)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.addFilter(_SecretFilter())
    logger.addHandler(fh)
