# OpenTelemetry Integration

ThothCTL supports OpenTelemetry for observability in non-interactive environments like CI/CD pipelines.

## Installation

```bash
pip install thothctl[telemetry]
```

## Configuration

### Environment Variables

```bash
# Enable telemetry
export THOTHCTL_OTEL_ENABLED=true

# Configure OTLP endpoint (default: http://localhost:4317)
export OTEL_EXPORTER_OTLP_ENDPOINT=https://your-otel-collector:4317

# Optional: Configure headers for authentication
export OTEL_EXPORTER_OTLP_HEADERS="authorization=Bearer your-token"
```

### Usage in CI/CD

```yaml
# GitHub Actions example
- name: Run ThothCTL with telemetry
  env:
    THOTHCTL_OTEL_ENABLED: true
    OTEL_EXPORTER_OTLP_ENDPOINT: ${{ secrets.OTEL_ENDPOINT }}
  run: |
    thothctl inventory iac --check-versions
    thothctl scan terraform
```

## What's Tracked

- **Command execution**: Start/end times, success/failure
- **Command arguments**: Sanitized command parameters
- **Errors**: Exception details and stack traces
- **Performance**: Execution duration and resource usage

## Supported Backends

- Jaeger
- Zipkin
- AWS X-Ray
- Google Cloud Trace
- Any OTLP-compatible collector

## Privacy

Telemetry is only enabled in non-interactive environments and when explicitly configured. No data is sent by default.
