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

## AI Review Tracing

The AI review service (`thothctl ai-review`) has dedicated OpenTelemetry instrumentation that produces a detailed span tree for every invocation. It uses the same `THOTHCTL_OTEL_ENABLED` environment variable and OTLP endpoint.

### Span Hierarchy

```
invocations (root)
├── orchestrator.run_agents
│   ├── orchestrator.execute_tasks
│   │   └── orchestrator.call_ai
│   │       └── provider.{name}.analyze    (bedrock | ollama | openai | azure | bedrock_agent)
│   └── decision_engine.evaluate
├── ai_agent.analyze_directory
│   └── provider.{name}.analyze
├── ai_agent.generate_fixes
│   └── provider.{name}.analyze
├── memory.save_analysis
└── memory.load_analysis
```

### Span Attributes

| Span | Attributes |
|------|-----------|
| `invocations` | `mode`, `directory`, `repository`, `run_id` |
| `orchestrator.run_agents` | `directory`, `roles` |
| `orchestrator.execute_tasks` | `task_count`, `parallel` |
| `orchestrator.call_ai` | `model`, `prompt_length` |
| `provider.*.analyze` | `model`, `region` (Bedrock), `input_tokens`, `output_tokens` |
| `ai_agent.analyze_directory` | `directory`, `findings_count` |
| `ai_agent.generate_fixes` | `directory`, `severity_filter`, `fixes_count` |
| `decision_engine.evaluate` | `repository`, `pr_id`, `decision`, `confidence` |
| `memory.save_analysis` | `repo`, `run_id`, `backend` |
| `memory.load_analysis` | `repo`, `run_id`, `backend`, `cache_hit` |

### Graceful Degradation

The tracing module (`thothctl.services.ai_review.tracing`) uses lazy initialization and no-op fallbacks. When OpenTelemetry packages are not installed or telemetry is disabled, all `span()` calls become zero-cost no-ops — no code changes or conditional logic needed in calling code.

### Example: Viewing Traces in Jaeger

```bash
# Start Jaeger all-in-one
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  jaegertracing/all-in-one:latest

# Run AI review with tracing
export THOTHCTL_OTEL_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
thothctl ai-review orchestrate -d ./terraform -a security -a fix

# Open Jaeger UI
open http://localhost:16686
# Search for service: thothctl-ai-review
```

## Supported Backends

- Jaeger
- Zipkin
- AWS X-Ray
- Google Cloud Trace
- Any OTLP-compatible collector

## Privacy

Telemetry is only enabled in non-interactive environments and when explicitly configured. No data is sent by default.
