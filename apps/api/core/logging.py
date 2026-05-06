"""
Structured JSON logging for production.

Why JSON? Coolify/Docker logs are line-oriented. JSON lines allow
log aggregation tools to parse fields (level, timestamp, message, etc.)
without custom parsers.

In development (DEBUG=True), we use a human-readable format instead
to avoid noisy JSON in local terminals.
"""

import logging
import sys
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    """
    Format log records as single-line JSON objects.

    Each line looks like:
        {"timestamp": "2024-01-01T00:00:00Z", "level": "INFO", "logger": "uvicorn", "message": "..."}
    """

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self.formatMessage(record),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def configure_logging(debug: bool = False) -> None:
    """
    Configure root logger.

    - Production (debug=False): JSON formatter → stdout
    - Development (debug=True): standard formatter → stdout (readable)
    """
    handler = logging.StreamHandler(sys.stdout)

    if debug:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
                datefmt="%H:%M:%S",
            )
        )
    else:
        handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Remove default handlers to avoid duplicate output
    root.handlers.clear()
    root.addHandler(handler)
