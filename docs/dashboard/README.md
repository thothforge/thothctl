# ThothCTL Dashboard

The ThothCTL Dashboard provides a unified web interface to view and manage all your infrastructure data in one place. It integrates scan results, inventory, cost analysis, drift detection, AI usage tracking, and risk assessments into a modern, responsive web application.

## Features

- **📊 Overview Dashboard**: Unified view of all infrastructure metrics
- **📦 Inventory Browser**: Collapsible stack groups with module/provider tabs, status filtering, and search
- **🔒 Security Findings Viewer**: Filter findings by tool, severity, and keyword search with pagination and inline report viewing
- **📋 SBOM Details Viewer**: Full CycloneDX 1.6 metadata including formulation, evidence, standards, attestations, and dependency graph
- **💰 Cost Analysis**: AWS cost estimates and optimization recommendations
- **⚠️ Risk Assessment**: Blast radius analysis and mitigation strategies
- **🔍 Drift Detection**: Infrastructure drift visualization between IaC and live cloud state
- **🤖 AI Token Usage**: Track AI provider token consumption and cost metrics
- **🔄 Real-time Refresh**: Manual data refresh capability
- **📱 Responsive Design**: Works on desktop, tablet, and mobile devices
- **🌙 Complete dark mode support**

## Quick Start

### Launch Dashboard
```bash
# Start dashboard on default port 8080
thothctl dashboard launch

# Custom port and host
thothctl dashboard launch --port 3000 --host 0.0.0.0

# Debug mode
thothctl dashboard launch --debug

# Don't open browser automatically
thothctl dashboard launch --no-browser
```

### Access Dashboard
Once launched, the dashboard will be available at:
- **Local**: http://127.0.0.1:8080
- **Network**: http://0.0.0.0:3000 (if using --host 0.0.0.0)

## Data Sources

The dashboard automatically loads data from existing ThothCTL reports:

### Inventory Data
- **Source**: `Reports/inventory/InventoryIaC_*.json`
- **Generate**: `thothctl inventory iac --check-versions`
- **Shows**: Infrastructure components, providers, versions, collapsible stack groups

### SBOM Data
- **Source**: `Reports/inventory/InventoryIaC_cyclonedx_*.json`
- **Generate**: `thothctl inventory iac --check-versions`
- **Shows**: CycloneDX 1.6 metadata — formulation, evidence, standards, attestations, dependency graph

### Security Scan Results
- **Source**: `Reports/**/*.html`, `Reports/**/*.xml`, `Reports/opa/html_reports/`
- **Generate**: `thothctl scan iac`
- **Shows**: Security issues, scan reports, compliance status — with filtering by tool/severity/search and inline report viewing via iframe

### Cost Analysis
- **Source**: `Reports/**/cost_analysis_*.json`
- **Generate**: `thothctl check iac -type cost-analysis`
- **Shows**: Monthly/annual costs, service breakdown, recommendations

### Risk Assessment
- **Source**: `Reports/**/blast_radius_*.json`
- **Generate**: `thothctl check project`
- **Shows**: Risk level, affected components, mitigation steps

### Drift Detection
- **Source**: `Reports/**/drift_*.json`
- **Generate**: `thothctl check iac -type drift --recursive`
- **Shows**: Drift between IaC definitions and live cloud resources, severity classification, coverage percentage

### AI Token Usage
- **Source**: `.thothctl/ai_sessions/`
- **Generate**: Collected automatically during `thothctl ai-review` operations
- **Shows**: Token consumption per provider, cost tracking, usage trends

## Enhanced Features (v0.19.0)

### Security Findings Viewer

The findings viewer provides granular access to individual security findings across all scanning tools:

- **Filter by tool**: Checkov, Trivy, TFSec, KICS
- **Filter by severity**: Critical, High, Medium, Low
- **Keyword search**: Search across finding titles, descriptions, and resource IDs
- **Pagination**: Navigate large result sets with configurable page size
- **Inline report viewing**: View full HTML reports in an iframe without leaving the dashboard

### SBOM Details Viewer

Full CycloneDX 1.6 support with rich metadata visualization:

- **Formulation**: How the software was built (build tools, environments)
- **Evidence**: Proof of component presence (call stacks, file occurrences)
- **Standards**: Compliance standards mappings (CIS, NIST, SOC2)
- **Attestations**: Signed assertions about software properties
- **Dependency Graph**: Interactive visualization of component relationships

### Inventory Browser

Enhanced inventory browsing experience:

- **Collapsible stack groups**: Organize components by stack for easier navigation
- **Module/Provider tabs**: Switch between module and provider views
- **Status filter**: Filter by up-to-date, outdated, or unknown status
- **Search**: Full-text search across all inventory items

### Drift Detection

Visualize infrastructure drift directly in the dashboard:

- Severity-based classification (critical/high/medium/low)
- IaC coverage percentage tracking
- Resource-level drift details
- Remediation guidance

### AI Token Usage

Monitor AI provider consumption:

- Per-provider token usage breakdown
- Cost tracking with daily/monthly views
- Usage trends over time
- Budget threshold indicators

## Architecture

### Twelve-Factor App Compliance

The dashboard follows twelve-factor app principles:

1. **Codebase**: Single codebase in version control
2. **Dependencies**: Explicitly declared (FastAPI, Uvicorn, etc.)
3. **Config**: Environment variables (THOTHCTL_DEBUG, THOTHCTL_VERBOSE)
4. **Backing Services**: File-based data sources as attached resources
5. **Build/Release/Run**: Separate stages
6. **Processes**: Stateless with in-memory caching
7. **Port Binding**: Self-contained service via Uvicorn
8. **Concurrency**: Scalable via Uvicorn workers and async handlers
9. **Disposability**: Fast startup/shutdown
10. **Dev/Prod Parity**: Same code in all environments
11. **Logs**: Event streams via Python logging
12. **Admin Processes**: Dashboard as admin interface

### Data Loading Strategy

```python
# Efficient file-based loading
class DashboardDataLoader:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    def get_inventory_data(self):
        # Load from Reports/inventory/InventoryIaC_*.json
        # Cache for 5 minutes
        # Graceful error handling
```

### Performance Features

- **Async I/O**: FastAPI async endpoints for non-blocking data loading
- **Smart Caching**: 5-minute TTL to avoid repeated I/O
- **Lazy Loading**: Data loaded only when requested
- **Graceful Degradation**: Helpful messages when data missing
- **Pagination**: Server-side pagination for large datasets (findings, inventory)

## API Endpoints

### Data Endpoints
- `GET /api/inventory` - Infrastructure inventory
- `GET /api/scan-results` - Security scan results
- `GET /api/findings?tool=&severity=&search=&limit=&offset=` - Individual findings with filtering and pagination
- `GET /api/sbom` - CycloneDX SBOM data
- `GET /api/cost-analysis` - Cost analysis data
- `GET /api/blast-radius` - Risk assessment data
- `GET /api/drift` - Drift detection data
- `GET /api/ai-usage` - AI token/cost usage
- `GET /api/reports/{path}` - Serve HTML reports for iframe viewing

### Control Endpoints
- `GET /api/refresh` - Clear cache and reload data
- `GET /` - Main dashboard interface

### Response Format
```json
{
  "components": [...],
  "summary": {...},
  "error": "Error message if any"
}
```

### Findings Response Format
```json
{
  "findings": [...],
  "total": 142,
  "limit": 20,
  "offset": 0,
  "filters": {
    "tool": "checkov",
    "severity": "high",
    "search": ""
  }
}
```

## Configuration

### Environment Variables
```bash
# Debug logging
export THOTHCTL_DEBUG=true

# Verbose logging  
export THOTHCTL_VERBOSE=true

# Custom host/port (can also use CLI flags)
# Default: 127.0.0.1:8080
```

### File Patterns
The dashboard looks for these file patterns:
```
Reports/
├── inventory/
│   ├── InventoryIaC_*.json              # Inventory data
│   ├── InventoryIaC_cyclonedx_*.json    # CycloneDX SBOM data
│   └── html_reports/                    # Inventory HTML reports
├── opa/
│   └── html_reports/                    # OPA/compliance HTML reports
├── cost_analysis_*.json                 # Cost analysis
├── blast_radius_*.json                  # Risk assessment
├── drift_*.json                         # Drift detection
├── **/*.html                            # Scan reports
└── **/*.xml                             # Test results
```

## Development

### Project Structure
```
src/thothctl/
├── commands/dashboard/
│   ├── cli.py                    # Command interface
│   └── commands/
│       └── launch.py             # Launch command
├── services/dashboard/
│   ├── dashboard_service.py      # FastAPI + Uvicorn web service
│   └── data_loader.py           # Data loading logic
└── utils/common/templates/
    └── dashboard.html           # Web interface
```

### Adding New Data Sources

1. **Extend DataLoader**:
```python
def get_new_data_source(self) -> Dict[str, Any]:
    cache_key = "new_source"
    if self._is_cache_valid(cache_key):
        return self.cache[cache_key]["data"]
    
    # Load from files
    data = load_from_files()
    self._cache_data(cache_key, data)
    return data
```

2. **Add API Endpoint**:
```python
@self.app.get("/api/new-source")
async def api_new_source():
    return self.data_loader.get_new_data_source()
```

3. **Update Frontend**:
```javascript
async function loadNewSourceData() {
    const response = await fetch('/api/new-source');
    const data = await response.json();
    // Update UI
}
```

## Troubleshooting

### Common Issues

**Dashboard won't start**
```bash
# Check if port is available
netstat -tulpn | grep :8080

# Try different port
thothctl dashboard launch --port 8081
```

**No data showing**
```bash
# Generate sample data first
thothctl inventory iac
thothctl scan iac  
thothctl check iac -type cost-analysis
thothctl check iac -type drift --recursive
```

**Permission errors**
```bash
# Check file permissions
ls -la Reports/
chmod 644 Reports/**/*.json
```

### Debug Mode
```bash
# Enable debug logging
export THOTHCTL_DEBUG=true
thothctl dashboard launch --debug
```

### Testing
```bash
# Test API endpoints
python test_dashboard.py

# Manual testing
curl http://localhost:8080/api/inventory
curl "http://localhost:8080/api/findings?tool=checkov&severity=high&limit=10"
curl http://localhost:8080/api/sbom
curl http://localhost:8080/api/drift
curl http://localhost:8080/api/ai-usage
```

## Security Considerations

- **Local Access**: Dashboard binds to 127.0.0.1 by default
- **No Authentication**: Intended for local development use
- **File Access**: Only reads from Reports directory
- **Report Serving**: HTML reports served via iframe are scoped to the Reports directory

## Integration Examples

### CI/CD Pipeline
```yaml
# .github/workflows/infrastructure.yml
- name: Generate Reports
  run: |
    thothctl inventory iac --check-versions
    thothctl scan iac
    thothctl check iac -type cost-analysis
    thothctl check iac -type drift --recursive

- name: Launch Dashboard
  run: |
    thothctl dashboard launch --no-browser --port 8080 &
    sleep 5
    curl http://localhost:8080/api/inventory
```

### Docker Integration
```dockerfile
FROM python:3.12-slim
COPY . /app
WORKDIR /app
RUN pip install -e .
EXPOSE 8080
CMD ["thothctl", "dashboard", "launch", "--host", "0.0.0.0"]
```

### Monitoring Integration
```bash
# Health check endpoint
curl -f http://localhost:8080/ || exit 1

# Data freshness check
curl http://localhost:8080/api/refresh
```

## Future Enhancements

- **Authentication**: Add user authentication
- **Real-time Updates**: WebSocket support for live data
- **Export Features**: PDF/Excel report generation
- **Alerting**: Integration with monitoring systems
- **Multi-project**: Support for multiple project dashboards
- **Plugins**: Extensible plugin architecture
