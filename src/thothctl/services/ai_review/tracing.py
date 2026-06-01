"""OpenTelemetry tracing for the AI Review agent service.

Provides a thin wrapper that gracefully degrades to no-ops when OTel
is not installed or not enabled.

Enable via:
    export THOTHCTL_OTEL_ENABLED=true
    export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317  # optional
"""
import os
import logging
from contextlib import contextmanager
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.trace import StatusCode, Span
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

_SERVICE_NAME = "thothctl-ai-review"
_tracer: Optional[Any] = None
_initialized = False


def _ensure_init():
    """Lazy-initialize the tracer on first use."""
    global _tracer, _initialized
    if _initialized:
        return
    _initialized = True

    if not OTEL_AVAILABLE:
        return
    if not os.getenv("THOTHCTL_OTEL_ENABLED", "").lower() in ("true", "1", "yes"):
        return

    try:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        resource = Resource.create({
            "service.name": _SERVICE_NAME,
            "service.version": _get_version(),
        })

        provider = TracerProvider(resource=resource)
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(_SERVICE_NAME)
        logger.info(f"OTel tracing enabled for {_SERVICE_NAME} → {endpoint}")
    except Exception as e:
        logger.warning(f"Failed to initialize OTel: {e}")


def _get_version() -> str:
    try:
        from importlib.metadata import version
        return version("thothctl")
    except Exception:
        return "unknown"


def get_tracer():
    """Return the OTel tracer (or None if disabled)."""
    _ensure_init()
    return _tracer


@contextmanager
def span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Context manager that creates a span if tracing is enabled.

    Usage:
        with span("orchestrator.run_agents", {"directory": d}):
            ...
    """
    _ensure_init()
    if _tracer is None:
        yield _NoOpSpan()
        return

    with _tracer.start_as_current_span(name) as s:
        if attributes:
            for k, v in attributes.items():
                if v is not None:
                    s.set_attribute(k, _safe_attr(v))
        try:
            yield s
        except Exception as exc:
            s.set_status(StatusCode.ERROR, str(exc))
            s.record_exception(exc)
            raise


def _safe_attr(v: Any) -> Any:
    """Coerce value to an OTel-compatible attribute type."""
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (list, tuple)):
        return [str(i) for i in v]
    return str(v)


class _NoOpSpan:
    """No-op span when tracing is disabled."""
    def set_attribute(self, key: str, value: Any):
        pass

    def set_status(self, *args, **kwargs):
        pass

    def record_exception(self, *args, **kwargs):
        pass

    def add_event(self, name: str, attributes=None):
        pass
