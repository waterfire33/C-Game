import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def configure_telemetry(engine=None) -> None:
    settings = get_settings()
    resource = Resource.create({"service.name": settings.otel_service_name, "deployment.environment": settings.app_env})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    if settings.otel_exporter_otlp_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=f"{settings.otel_exporter_otlp_endpoint.rstrip('/')}/v1/traces")
            )
        )

    trace.set_tracer_provider(provider)
    LoggingInstrumentor().instrument(set_logging_format=True)
    RedisInstrumentor().instrument()

    if engine is not None:
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)

    logger.info("OpenTelemetry configured", extra={"service": settings.otel_service_name})


def instrument_fastapi(app) -> None:
    FastAPIInstrumentor.instrument_app(app)
