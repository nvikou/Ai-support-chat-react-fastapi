"""OpenTelemetry tracing setup and span helpers.

HTTP spans come from FastAPI instrumentation. Business spans
(retrieval → LLM → groundedness → confidence) are opened manually
so the answer path stays readable in Jaeger/Tempo.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import Span, Status, StatusCode

from app.config import Settings
from app.observability.logging import get_request_id

logger = logging.getLogger(__name__)

_TRACER_NAME = "vatecon"
_provider: TracerProvider | None = None


def setup_tracing(settings: Settings, app: Any | None = None) -> None:
    """Configure TracerProvider + optional FastAPI instrumentation.

    No-op when ``otel_enabled`` is false so offline tests stay quiet.
    """
    global _provider
    if not settings.otel_enabled:
        return
    if _provider is not None:
        return

    resource = Resource.create(
        {
            "service.name": "vatecon-api",
            "service.version": "1.0.0",
            "deployment.environment": settings.environment,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter_name = settings.otel_exporter.lower().strip()
    if exporter_name == "otlp":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        endpoint = settings.otel_endpoint.rstrip("/")
        # SDK expects the full traces URL or base; pass as configured.
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    elif exporter_name == "console":
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    else:
        raise ValueError(
            f"Unsupported otel_exporter={settings.otel_exporter!r}; "
            "use 'console' or 'otlp'"
        )

    trace.set_tracer_provider(provider)
    _provider = provider

    if app is not None:
        from opentelemetry.instrumentation.fastapi import (
            FastAPIInstrumentor,
        )

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="health,metrics",
        )

    logger.info(
        "otel_tracing_enabled",
        extra={
            "event": "otel_tracing_enabled",
            "exporter": exporter_name,
        },
    )


def shutdown_tracing() -> None:
    """Flush and shut down the process TracerProvider."""
    global _provider
    if _provider is None:
        return
    _provider.shutdown()
    _provider = None


def get_tracer() -> trace.Tracer:
    return trace.get_tracer(_TRACER_NAME)


@contextmanager
def span(
    name: str,
    **attributes: Any,
) -> Iterator[Span]:
    """Open a child span; safe no-op when tracing is disabled."""
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as current:
        request_id = get_request_id()
        if request_id is not None:
            current.set_attribute("request.id", request_id)
        for key, value in attributes.items():
            if value is None:
                continue
            current.set_attribute(key, value)
        try:
            yield current
        except Exception as exc:
            current.record_exception(exc)
            current.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
