"""
ThothCTL Color Matrix - Unified color system for all reports and dashboards
"""

THOTH_COLORS = """
    :root {
        /* Primary Brand Colors */
        --thoth-primary: #667eea;
        --thoth-secondary: #764ba2;
        
        /* Status Colors */
        --status-success: #10b981;
        --status-warning: #f59e0b;
        --status-error: #ef4444;
        --status-info: #3b82f6;
        --status-neutral: #6b7280;
        
        /* Infrastructure Actions */
        --action-create: #06b6d4;
        --action-update: #f59e0b;
        --action-delete: #ef4444;
        --action-noop: #6b7280;
        
        /* Cost Analysis */
        --cost-low: #10b981;
        --cost-medium: #f59e0b;
        --cost-high: #f97316;
        --cost-critical: #dc2626;
        
        /* Confidence Levels */
        --confidence-high: #10b981;
        --confidence-medium: #f59e0b;
        --confidence-low: #ef4444;
        
        /* Compliance/Security */
        --severity-critical: #dc2626;
        --severity-high: #ef4444;
        --severity-medium: #f59e0b;
        --severity-low: #fbbf24;
        --severity-info: #3b82f6;
        
        /* Backgrounds */
        --bg-primary: #ffffff;
        --bg-secondary: #f9fafb;
        --bg-tertiary: #f3f4f6;
        --bg-dark: #111827;
        
        /* Text */
        --text-primary: #111827;
        --text-secondary: #6b7280;
        --text-tertiary: #9ca3af;
        --text-inverse: #ffffff;
        
        /* Borders */
        --border-light: #e5e7eb;
        --border-medium: #d1d5db;
        --border-dark: #9ca3af;
        
        /* Service-Specific Colors */
        --service-compute: #ff9900;
        --service-storage: #569a31;
        --service-database: #527fff;
        --service-network: #8c4fff;
        --service-security: #dd344c;
        --service-container: #0073bb;
        
        /* Chart Colors */
        --chart-1: #667eea;
        --chart-2: #06b6d4;
        --chart-3: #10b981;
        --chart-4: #f59e0b;
        --chart-5: #ef4444;
        --chart-6: #8b5cf6;
        --chart-7: #ec4899;
        --chart-8: #14b8a6;
    }
"""

def get_cost_color(amount: float) -> str:
    """Get color based on cost amount"""
    if amount < 100:
        return "var(--cost-low)"
    elif amount < 500:
        return "var(--cost-medium)"
    elif amount < 1000:
        return "var(--cost-high)"
    else:
        return "var(--cost-critical)"

def get_severity_color(severity: str) -> str:
    """Get color based on severity level"""
    severity_map = {
        "critical": "var(--severity-critical)",
        "high": "var(--severity-high)",
        "medium": "var(--severity-medium)",
        "low": "var(--severity-low)",
        "info": "var(--severity-info)",
    }
    return severity_map.get(severity.lower(), "var(--status-neutral)")

def get_status_color(status: str) -> str:
    """Get color based on status"""
    status_map = {
        "success": "var(--status-success)",
        "current": "var(--status-success)",
        "passing": "var(--status-success)",
        "warning": "var(--status-warning)",
        "outdated": "var(--status-warning)",
        "error": "var(--status-error)",
        "failed": "var(--status-error)",
        "critical": "var(--status-error)",
        "info": "var(--status-info)",
        "unknown": "var(--status-neutral)",
    }
    return status_map.get(status.lower(), "var(--status-neutral)")
