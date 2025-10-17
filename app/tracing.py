"""
OpenTelemetry configuration and utilities for Procrastinate job tracing.

This module provides:
- OpenTelemetry setup with Jaeger exporter
- Trace context propagation utilities
- Custom instrumentation for Procrastinate jobs
"""

import os
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

from opentelemetry import trace, context
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
try:
    from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)

# Global tracer instance
tracer: Optional[trace.Tracer] = None


def setup_tracing(
    service_name: str = "procrastinate-demo",
    jaeger_endpoint: str = "http://localhost:14268/api/traces",
    enable_console: bool = False
) -> trace.Tracer:
    """
    Initialize OpenTelemetry tracing with Jaeger exporter.
    
    Args:
        service_name: Name of the service for tracing
        jaeger_endpoint: Jaeger collector endpoint
        enable_console: Whether to enable console exporter for debugging
        
    Returns:
        Configured tracer instance
    """
    global tracer
    
    # Create resource with service information
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
    })
    
    # Set up tracer provider
    trace.set_tracer_provider(TracerProvider(resource=resource))
    
    # Configure Jaeger exporter
    jaeger_exporter = JaegerExporter(
        collector_endpoint=jaeger_endpoint,
    )
    
    # Add span processor
    span_processor = BatchSpanProcessor(jaeger_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)
    
    # Optional console exporter for debugging
    if enable_console:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        console_exporter = ConsoleSpanExporter()
        console_processor = BatchSpanProcessor(console_exporter)
        trace.get_tracer_provider().add_span_processor(console_processor)
    
    # Auto-instrument libraries
    HTTPXClientInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()
    if PSYCOPG2_AVAILABLE:
        Psycopg2Instrumentor().instrument()
    else:
        logger.info("psycopg2 instrumentation not available (using psycopg3)")
    
    # Create tracer
    tracer = trace.get_tracer(__name__)
    
    logger.info(f"OpenTelemetry tracing initialized for service: {service_name}")
    return tracer


def get_tracer() -> trace.Tracer:
    """Get the global tracer instance."""
    global tracer
    if tracer is None:
        tracer = setup_tracing()
    return tracer


def inject_trace_context() -> Dict[str, str]:
    """
    Extract current trace context and return it as a dictionary.
    This can be passed as extra arguments to Procrastinate jobs.
    
    Returns:
        Dictionary containing trace context headers
    """
    carrier = {}
    TraceContextTextMapPropagator().inject(carrier)
    return carrier


def extract_trace_context(carrier: Dict[str, str]) -> None:
    """
    Extract trace context from carrier and set it as current context.
    
    Args:
        carrier: Dictionary containing trace context headers
    """
    if carrier:
        ctx = TraceContextTextMapPropagator().extract(carrier)
        context.attach(ctx)


@contextmanager
def trace_job_execution(job_name: str, job_id: Optional[str] = None, **attributes):
    """
    Context manager to trace job execution with proper span management.
    
    Args:
        job_name: Name of the job being executed
        job_id: Optional job ID for correlation
        **attributes: Additional span attributes
    """
    tracer = get_tracer()
    
    span_name = f"procrastinate.job.{job_name}"
    with tracer.start_as_current_span(span_name) as span:
        # Set standard attributes
        span.set_attribute("job.name", job_name)
        span.set_attribute("job.system", "procrastinate")
        
        if job_id:
            span.set_attribute("job.id", str(job_id))
        
        # Set custom attributes
        for key, value in attributes.items():
            span.set_attribute(f"job.{key}", str(value))
        
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise


def trace_job_defer(job_name: str, **kwargs) -> Dict[str, str]:
    """
    Create a span for job deferral and return trace context.
    
    Args:
        job_name: Name of the job being deferred
        **kwargs: Job arguments
        
    Returns:
        Trace context to be passed to the job
    """
    tracer = get_tracer()
    
    with tracer.start_as_current_span(f"procrastinate.defer.{job_name}") as span:
        span.set_attribute("job.name", job_name)
        span.set_attribute("job.system", "procrastinate")
        span.set_attribute("job.operation", "defer")
        
        # Add job arguments as attributes (be careful with sensitive data)
        for key, value in kwargs.items():
            if not key.startswith('_') and len(str(value)) < 100:  # Avoid large values
                span.set_attribute(f"job.arg.{key}", str(value))
        
        # Return current trace context
        return inject_trace_context()


def get_current_trace_id() -> Optional[str]:
    """
    Get the current trace ID if available.
    
    Returns:
        Trace ID as hex string or None if no active trace
    """
    current_span = trace.get_current_span()
    if current_span and current_span.get_span_context().is_valid:
        return format(current_span.get_span_context().trace_id, '032x')
    return None


def get_current_span_id() -> Optional[str]:
    """
    Get the current span ID if available.
    
    Returns:
        Span ID as hex string or None if no active span
    """
    current_span = trace.get_current_span()
    if current_span and current_span.get_span_context().is_valid:
        return format(current_span.get_span_context().span_id, '016x')
    return None
