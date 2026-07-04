from __future__ import annotations

import logging

from app.core.trace import get_trace_id


class TraceIdFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.trace_id = get_trace_id() or "-"
        return super().format(record)


def configure_logging(level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level.upper())

    handler = logging.StreamHandler()
    handler.setLevel(level.upper())
    handler.setFormatter(
        TraceIdFormatter(
            "%(asctime)s %(levelname)s %(name)s trace_id=%(trace_id)s %(message)s"
        )
    )
    root_logger.addHandler(handler)

