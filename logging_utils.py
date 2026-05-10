import contextvars
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

_request_id_ctx_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in {
                "name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
                "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
                "relativeCreated", "thread", "threadName", "processName", "process", "message",
            }:
                continue
            payload[key] = value
        return json.dumps(payload, default=str)


def get_request_id() -> str:
    return _request_id_ctx_var.get() or "-"


def set_request_id(request_id: Optional[str]):
    return _request_id_ctx_var.set(request_id)


def reset_request_id(token):
    _request_id_ctx_var.reset(token)


def configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_format = os.getenv("LOG_FORMAT", "json").lower()

    handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s [request_id=%(request_id)s] %(message)s"
        ))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    has_filter = any(isinstance(log_filter, RequestIdFilter) for log_filter in logger.filters)
    if not has_filter:
        logger.addFilter(RequestIdFilter())
    return logger
