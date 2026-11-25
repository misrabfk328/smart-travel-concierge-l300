# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Structured JSON logging with OTel trace context and active PII scrubbing."""

from __future__ import annotations

import logging
import os
from typing import Any

from opentelemetry import trace
from pythonjsonlogger.json import JsonFormatter

from app.security.pii import PiiRedactor


class PiiScrubbingJsonFormatter(JsonFormatter):
    """Formats log records as single-line JSON with OTel IDs and PII redaction."""

    def __init__(
        self, *args: Any, redactor: PiiRedactor | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self._redactor = redactor or PiiRedactor()

    def add_fields(
        self,
        log_data: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_data, record, message_dict)
        log_data.setdefault("severity", record.levelname)
        log_data.setdefault("logger", record.name)
        log_data.setdefault(
            "service",
            os.environ.get("OTEL_SERVICE_NAME", "smart-travel-concierge-l300"),
        )

        span = trace.get_current_span()
        ctx = span.get_span_context() if span is not None else None
        if ctx is not None and ctx.is_valid:
            log_data["trace_id"] = format(ctx.trace_id, "032x")
            log_data["span_id"] = format(ctx.span_id, "016x")

        # Scrub every field in the outgoing JSON record before emission.
        for key, value in list(log_data.items()):
            log_data[key] = self._redactor.redact_value(value)


def configure_structured_logging(level: str | None = None) -> logging.Logger:
    """Configure root/app loggers with structured PII-scrubbed JSON formatting."""
    resolved_level = getattr(
        logging,
        (level or os.environ.get("LOG_LEVEL", "INFO")).upper(),
        logging.INFO,
    )
    app_logger = logging.getLogger("app")
    app_logger.setLevel(resolved_level)

    if not any(
        isinstance(getattr(h, "formatter", None), PiiScrubbingJsonFormatter)
        for h in app_logger.handlers
    ):
        handler = logging.StreamHandler()
        handler.setFormatter(
            PiiScrubbingJsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                rename_fields={"asctime": "timestamp", "levelname": "level"},
            )
        )
        app_logger.handlers.clear()
        app_logger.addHandler(handler)
        app_logger.propagate = False

    return app_logger
