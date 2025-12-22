"""OpenTelemetry integration for ThothCTL."""
import logging
import os
from typing import Optional

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


class TelemetryManager:
    """Manages OpenTelemetry integration for ThothCTL."""
    
    def __init__(self):
        self.enabled = False
        self.tracer: Optional[trace.Tracer] = None
        
    def initialize(self) -> bool:
        """Initialize OpenTelemetry if enabled and available."""
        if not OTEL_AVAILABLE:
            return False
            
        # Check if telemetry is enabled via environment
        if not os.getenv("THOTHCTL_OTEL_ENABLED", "").lower() in ("true", "1", "yes"):
            return False
            
        try:
            # Configure resource
            resource = Resource.create({
                "service.name": "thothctl",
                "service.version": self._get_version(),
            })
            
            # Set up tracer provider
            trace.set_tracer_provider(TracerProvider(resource=resource))
            
            # Configure exporter
            endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
            exporter = OTLPSpanExporter(endpoint=endpoint)
            
            # Add span processor
            span_processor = BatchSpanProcessor(exporter)
            trace.get_tracer_provider().add_span_processor(span_processor)
            
            # Get tracer
            self.tracer = trace.get_tracer(__name__)
            
            # Instrument logging
            LoggingInstrumentor().instrument(set_logging_format=True)
            
            self.enabled = True
            return True
            
        except Exception as e:
            logging.warning(f"Failed to initialize OpenTelemetry: {e}")
            return False
    
    def _get_version(self) -> str:
        """Get ThothCTL version."""
        try:
            from importlib.metadata import version
            return version('thothctl')
        except Exception:
            return "unknown"
    
    def start_span(self, name: str, **attributes):
        """Start a new span if telemetry is enabled."""
        if self.enabled and self.tracer:
            return self.tracer.start_as_current_span(name, attributes=attributes)
        return _NoOpSpan()


class _NoOpSpan:
    """No-op span for when telemetry is disabled."""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def set_attribute(self, key, value):
        pass
    def set_status(self, status):
        pass


# Global telemetry manager
telemetry = TelemetryManager()
