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

"""OpenTelemetry distributed tracing setup with Cloud Trace and local span capture."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

from app.security.pii import PiiRedactor

_LOGGER = logging.getLogger(__name__)
_REDACTOR = PiiRedactor()
_TRACING_CONFIGURED = False


class InMemorySpanRecorder(SpanExporter):
    """Thread-safe local span recorder for inspection and unit tests."""

    def __init__(self, max_spans: int = 500) -> None:
        self._spans: list[Any] = []
        self._max_spans = max_spans

    def export(self, spans: Any) -> SpanExportResult:
        for span in spans:
            self._spans.append(span)
        if len(self._spans) > self._max_spans:
            self._spans = self._spans[-self._max_spans :]
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def get_finished_spans(self) -> list[Any]:
        return list(self._spans)

    def clear(self) -> None:
        self._spans.clear()


_SPAN_RECORDER = InMemorySpanRecorder()


def get_recorded_spans() -> list[Any]:
    """Return recorded OpenTelemetry spans from the in-process exporter."""
    return _SPAN_RECORDER.get_finished_spans()


def clear_recorded_spans() -> None:
    """Clear recorded spans (for test isolation)."""
    _SPAN_RECORDER.clear()


def configure_tracing(
    service_name: str = "smart-travel-concierge-l300",
) -> trace.Tracer:
    """Initialize OpenTelemetry TracerProvider with Cloud Trace + local span capture."""
    global _TRACING_CONFIGURED
    if not _TRACING_CONFIGURED:
        resource = Resource.create(
            {
                "service.name": os.environ.get("OTEL_SERVICE_NAME", service_name),
                "service.version": os.environ.get("AGENT_VERSION", "0.1.0"),
            }
        )
        current_provider = trace.get_tracer_provider()
        if isinstance(current_provider, TracerProvider):
            provider = current_provider
        else:
            provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(provider)

        provider.add_span_processor(SimpleSpanProcessor(_SPAN_RECORDER))

        enable_cloud_trace = os.environ.get(
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY", ""
        ).lower() in ("true", "1", "yes")
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        if enable_cloud_trace and project_id and project_id != "your-gcp-project-id":
            try:
                from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

                provider.add_span_processor(
                    BatchSpanProcessor(CloudTraceSpanExporter(project_id=project_id))
                )
            except Exception as exc:  # pragma: no cover - optional cloud exporter
                _LOGGER.warning("CloudTraceSpanExporter unavailable: %s", exc)

        _TRACING_CONFIGURED = True

    return trace.get_tracer("app.travel_concierge")


@contextmanager
def trace_span(
    name: str,
    attributes: Mapping[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Create a PII-scrubbed OpenTelemetry span for an agent/tool operation."""
    tracer = configure_tracing()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                sanitized = _REDACTOR.redact_value(value)
                if isinstance(sanitized, (str, bool, int, float)):
                    span.set_attribute(key, sanitized)
                elif sanitized is not None:
                    span.set_attribute(key, str(sanitized))
        yield span
