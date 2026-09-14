"""Optional OTLP tracing for API, provider HTTP, SQLAlchemy and Redis calls."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import FastAPI

from config import get_settings

_configured = False


def _headers(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in raw.split(","):
        if not item.strip():
            continue
        key, separator, value = item.partition("=")
        if not separator or not key.strip():
            raise RuntimeError("OTEL_EXPORTER_OTLP_HEADERS must use key=value pairs")
        result[key.strip()] = value.strip()
    return result


def configure_otel(app: FastAPI) -> None:
    """Configure tracing once. No request/response bodies or auth headers are captured."""
    global _configured
    settings = get_settings()
    if not settings.otel_enabled or _configured:
        return
    endpoint = settings.otel_exporter_otlp_endpoint.rstrip("/")
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("OTEL_EXPORTER_OTLP_ENDPOINT must be an HTTP(S) URL")

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.otel_service_name}),
        sampler=ParentBased(TraceIdRatioBased(settings.otel_trace_sample_ratio)),
    )
    exporter = OTLPSpanExporter(
        endpoint=f"{endpoint}/v1/traces",
        headers=_headers(settings.otel_exporter_otlp_headers),
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    from db.database import engine

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/api/health,/api/ready,/api/ping,/api/metrics.*",
    )
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()
    _configured = True
