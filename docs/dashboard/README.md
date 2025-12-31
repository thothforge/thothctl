# ThothCTL Dashboard

The ThothCTL Dashboard provides a unified web interface to view and manage all your infrastructure data in one place. It integrates scan results, inventory, cost analysis, and risk assessments into a modern, responsive web application.

## Features

- **📊 Overview Dashboard**: Unified view of all infrastructure metrics
- **📦 Inventory Management**: View infrastructure components and providers
- **🔒 Security Results**: Display scan results from Checkov, Trivy, and other tools
- **💰 Cost Analysis**: AWS cost estimates and optimization recommendations
- **⚠️ Risk Assessment**: Blast radius analysis and mitigation strategies
- **🔄 Real-time Refresh**: Manual data refresh capability
- **📱 Responsive Design**: Works on desktop, tablet, and mobile devices

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
- **Source**: `Reports/**/InventoryIaC_*.json`
- **Generate**: `thothctl inventory iac --check-versions`
- **Shows**: Infrastructure components, providers, versions

### Security Scan Results
- **Source**: `Reports/**/*.html`, `Reports/**/*.xml`
- **Generate**: `thothctl scan iac`
- **Shows**: Security issues, scan reports, compliance status

### Cost Analysis
- **Source**: `Reports/**/cost_analysis_*.json`
- **Generate**: `thothctl check iac -type cost-analysis`
- **Shows**: Monthly/annual costs, service breakdown, recommendations

### Risk Assessment
- **Source**: `Reports/**/blast_radius_*.json`
- **Generate**: `thothctl check project`
- **Shows**: Risk level, affected components, mitigation steps

## Architecture

### Twelve-Factor App Compliance

The dashboard follows twelve-factor app principles:

1. **Codebase**: Single codebase in version control
2. **Dependencies**: Explicitly declared (Flask, etc.)
3. **Config**: Environment variables (THOTHCTL_SECRET_KEY)
4. **Backing Services**: File-based data sources as attached resources
5. **Build/Release/Run**: Separate stages
6. **Processes**: Stateless with in-memory caching
7. **Port Binding**: Self-contained service
8. **Concurrency**: Scalable via process model
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
        # Load from Reports/InventoryIaC_*.json
        # Cache for 5 minutes
        # Graceful error handling
```

### Performance Features

- **File-based Loading**: No expensive service calls on startup
- **Smart Caching**: 5-minute TTL to avoid repeated I/O
- **Lazy Loading**: Data loaded only when requested
- **Graceful Degradation**: Helpful messages when data missing

## API Endpoints

### Data Endpoints
- `GET /api/inventory` - Infrastructure inventory
- `GET /api/scan-results` - Security scan results  
- `GET /api/cost-analysis` - Cost analysis data
- `GET /api/blast-radius` - Risk assessment data

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

## Configuration

### Environment Variables
```bash
# Security key for Flask sessions
export THOTHCTL_SECRET_KEY="your-secret-key"

# Debug logging
export THOTHCTL_DEBUG=true

# Verbose logging  
export THOTHCTL_VERBOSE=true
```

### File Patterns
The dashboard looks for these file patterns:
```
Reports/
├── InventoryIaC_*.json      # Inventory data
├── cost_analysis_*.json     # Cost analysis
├── blast_radius_*.json      # Risk assessment
├── **/*.html               # Scan reports
└── **/*.xml                # Test results
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
│   ├── dashboard_service.py      # Flask web service
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
@self.app.route('/api/new-source')
def api_new_source():
    return jsonify(self.data_loader.get_new_data_source())
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
```

**Permission errors**
```bash
# Check file permissions
ls -la Reports/
chmod 644 Reports/*.json
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
```

## Security Considerations

- **Local Access**: Dashboard binds to 127.0.0.1 by default
- **No Authentication**: Intended for local development use
- **File Access**: Only reads from Reports directory
- **Secret Key**: Use environment variable in production

## Integration Examples

### CI/CD Pipeline
```yaml
# .github/workflows/infrastructure.yml
- name: Generate Reports
  run: |
    thothctl inventory iac --check-versions
    thothctl scan iac
    thothctl check iac -type cost-analysis

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
