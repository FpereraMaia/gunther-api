"""OpenTelemetry SDK initialization.

Pipeline:
  Traces  — OTel SDK → OTLP gRPC → Grafana Alloy → Tempo
  Metrics — OTel SDK → PrometheusMetricReader → /metrics endpoint → Prometheus scrape
  Logs    — structlog JSON → stdout → Docker → Alloy (docker log collector) → Loki
            (see logging.py — logs don't use OTel SDK to keep structlog ergonomics)

Call setup_telemetry() once at application startup, before any other imports,
so instrumentation patches are applied at the earliest possible point.
"""

from __future__ import annotations

from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes

from app.shared.config import Settings


def setup_telemetry(settings: Settings) -> None:
    """Initialize OTel tracing and metrics. Must run before FastAPI/SQLAlchemy imports."""
    resource = _build_resource(settings)
    _setup_tracing(resource, settings)
    _setup_metrics(resource)
    _instrument_libraries()


def _build_resource(settings: Settings) -> Resource:
    return Resource.create(
        {
            ResourceAttributes.SERVICE_NAME: settings.otel_service_name,
            ResourceAttributes.SERVICE_VERSION: settings.otel_service_version,
            "deployment.environment": settings.otel_environment,
        }
    )


def _setup_tracing(resource: Resource, settings: Settings) -> None:
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def _setup_metrics(resource: Resource) -> None:
    reader = PrometheusMetricReader()
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)


def _instrument_libraries() -> None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    FastAPIInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    RedisInstrumentor().instrument()


def make_metrics_asgi_app() -> Any:
    """Return an ASGI app that serves Prometheus-format metrics at /metrics."""
    from prometheus_client import make_asgi_app

    return make_asgi_app()
