"""Centralized logging configuration for KnowledgeForge.

Reads settings from config.yaml via get_config() and sets up:
  - Console handler (always on)
  - Rotating file handler (when config.logging.file_enabled = true)
  - JSON formatter (when config.logging.json_format = true)
  - Standard format string otherwise

Call setup_logging() once at application startup.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
from pathlib import Path
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt or "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include request_id if it was injected by the middleware
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_data["request_id"] = request_id

        if record.exc_info:
            log_data["exc_info"] = self.formatException(record.exc_info)

        # Extra fields attached via logger.info("msg", extra={...})
        skip = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "request_id",
        }
        for key, value in record.__dict__.items():
            if key not in skip:
                log_data[key] = value

        return json.dumps(log_data, default=str)


def setup_logging(config=None) -> None:
    """Configure root logger from config.  Safe to call multiple times."""
    # Defaults
    level_str = "INFO"
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    use_json = False
    file_enabled = False
    file_path = "./logs/api.log"
    max_bytes = 10 * 1024 * 1024  # 10 MB
    backup_count = 5
    console_enabled = True

    if config is not None:
        log_cfg = getattr(config, "logging", None)
        if log_cfg:
            level_str = str(getattr(log_cfg, "level", level_str)).upper()
            fmt = str(getattr(log_cfg, "format", fmt))
            use_json = bool(getattr(log_cfg, "json_format", use_json))
            file_enabled = bool(getattr(log_cfg, "file_enabled", file_enabled))
            file_path = str(getattr(log_cfg, "file_path", file_path))
            max_mb = getattr(log_cfg, "max_file_size_mb", 10)
            max_bytes = int(max_mb) * 1024 * 1024
            backup_count = int(getattr(log_cfg, "backup_count", backup_count))
            console_enabled = bool(getattr(log_cfg, "console_enabled", console_enabled))

    level = getattr(logging, level_str, logging.INFO)

    # Choose formatter
    formatter: logging.Formatter
    if use_json:
        formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(fmt)

    root = logging.getLogger()
    # Remove existing handlers added by earlier basicConfig / uvicorn
    root.handlers.clear()
    root.setLevel(level)

    if console_enabled:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(formatter)
        root.addHandler(ch)

    if file_enabled:
        log_dir = Path(file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(formatter)
        root.addHandler(fh)

    # Silence noisy third-party loggers
    for noisy in ("urllib3", "httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
