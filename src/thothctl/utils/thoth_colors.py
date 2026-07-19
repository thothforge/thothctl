"""
ThothCTL Color Matrix - Single source of truth for all reports and dashboards.

All HTML templates, CSS files, and Python report generators MUST consume colors
from this module. Never hard-code hex values elsewhere.

Usage:
    from thothctl.utils.thoth_colors import THOTH_COLORS, THOTH_DARK_MODE, get_full_css
"""

# =============================================================================
# LIGHT MODE (default) - CSS Custom Properties
# =============================================================================
THOTH_COLORS = """
    :root {
        /* ─── Brand Identity ─── */
        --thoth-primary: #667eea;
        --thoth-secondary: #764ba2;
        --thoth-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        --thoth-gradient-header: linear-gradient(135deg, #667eea, #764ba2);

        /* ─── Semantic Status ─── */
        --status-success: #10b981;
        --status-warning: #f59e0b;
        --status-error: #ef4444;
        --status-info: #3b82f6;
        --status-neutral: #6b7280;
        /* Text-safe variants (WCAG AA 4.5:1 on white) */
        --status-success-text: #047857;
        --status-warning-text: #b45309;
        --status-error-text: #dc2626;
        --status-info-text: #1d4ed8;
        --status-neutral-text: #4b5563;

        /* ─── Infrastructure Actions ─── */
        --action-create: #06b6d4;
        --action-update: #f59e0b;
        --action-delete: #ef4444;
        --action-noop: #6b7280;

        /* ─── Cost Analysis ─── */
        --cost-low: #10b981;
        --cost-medium: #f59e0b;
        --cost-high: #f97316;
        --cost-critical: #dc2626;
        /* Text-safe variants (WCAG AA 4.5:1 on white) */
        --cost-low-text: #047857;
        --cost-medium-text: #b45309;
        --cost-high-text: #c2410c;
        --cost-critical-text: #991b1b;

        /* ─── Confidence Levels ─── */
        --confidence-high: #10b981;
        --confidence-medium: #f59e0b;
        --confidence-low: #ef4444;

        /* ─── Compliance / Security Severity ─── */
        --severity-critical: #dc2626;
        --severity-high: #ef4444;
        --severity-medium: #f59e0b;
        --severity-low: #fbbf24;
        --severity-info: #3b82f6;
        /* Text-safe variants (WCAG AA 4.5:1 on white) */
        --severity-critical-text: #991b1b;
        --severity-high-text: #dc2626;
        --severity-medium-text: #b45309;
        --severity-low-text: #a16207;
        --severity-info-text: #1d4ed8;

        /* ─── Backgrounds ─── */
        --bg-primary: #ffffff;
        --bg-secondary: #f9fafb;
        --bg-tertiary: #f3f4f6;
        --bg-dark: #111827;

        /* ─── Text ─── */
        --text-primary: #111827;
        --text-secondary: #6b7280;
        --text-tertiary: #7c8490;  /* 3.78:1 on white — passes AA Large */
        --text-placeholder: #9ca3af;  /* Decorative only — below WCAG for readable text */
        --text-inverse: #ffffff;

        /* ─── Borders ─── */
        --border-light: #e5e7eb;
        --border-medium: #d1d5db;
        --border-dark: #9ca3af;

        /* ─── AWS Service Colors ─── */
        --service-compute: #ff9900;
        --service-storage: #569a31;
        --service-database: #527fff;
        --service-network: #8c4fff;
        --service-security: #dd344c;
        --service-container: #0073bb;

        /* ─── Chart Palette (8 distinct) ─── */
        --chart-1: #667eea;
        --chart-2: #06b6d4;
        --chart-3: #10b981;
        --chart-4: #f59e0b;
        --chart-5: #ef4444;
        --chart-6: #8b5cf6;
        --chart-7: #ec4899;
        --chart-8: #14b8a6;

        /* ─── Layout Tokens ─── */
        --radius: 8px;
        --radius-sm: 4px;
        --radius-lg: 12px;
        --radius-pill: 20px;
        --shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        --shadow-lg: 0 20px 60px rgba(0, 0, 0, 0.15);
        --transition: all 0.2s ease;

        /* ─── Legacy Aliases (for backward compatibility) ─── */
        --primary-color: var(--thoth-primary);
        --secondary-color: var(--text-secondary);
        --success-color: var(--status-success);
        --warning-color: var(--status-warning);
        --danger-color: var(--status-error);
        --info-color: var(--status-info);
        --light-color: var(--bg-secondary);
        --dark-color: var(--text-primary);
        --primary: var(--thoth-primary);
        --secondary: var(--text-secondary);
        --success: var(--status-success);
        --warning: var(--status-warning);
        --danger: var(--status-error);
        --info: var(--status-info);
        --bg: var(--bg-secondary);
        --dark: var(--text-primary);
        --box-shadow: var(--shadow);
        --border-radius: var(--radius);
    }
"""

# =============================================================================
# DARK MODE - CSS overrides for prefers-color-scheme and .dark-mode class
# =============================================================================
THOTH_DARK_MODE = """
    @media (prefers-color-scheme: dark) {
        :root {
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-tertiary: #64748b;
            --border-light: #334155;
            --border-medium: #475569;
            --border-dark: #64748b;
            --shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
            --shadow-lg: 0 20px 60px rgba(0, 0, 0, 0.5);
        }
    }

    body.dark-mode {
        --bg-primary: #0f172a;
        --bg-secondary: #1e293b;
        --bg-tertiary: #334155;
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --text-tertiary: #64748b;
        --border-light: #334155;
        --border-medium: #475569;
        --border-dark: #64748b;
        --shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        --shadow-lg: 0 20px 60px rgba(0, 0, 0, 0.5);
    }

    body.dark-mode {
        background: #0f172a;
    }
    body.dark-mode .container {
        background: var(--bg-secondary);
        color: var(--text-primary);
    }
    body.dark-mode .nav-header {
        background: var(--thoth-gradient-header);
    }
    body.dark-mode .card,
    body.dark-mode .summary-card {
        background: var(--bg-tertiary);
        border-color: var(--border-light);
        color: var(--text-primary);
    }
    body.dark-mode .card-number,
    body.dark-mode .summary-number {
        opacity: 1;
    }
    body.dark-mode .card-label,
    body.dark-mode .summary-label {
        color: var(--text-secondary);
    }
    body.dark-mode .data-table th,
    body.dark-mode .components-table th,
    body.dark-mode .findings-table th {
        background: var(--bg-tertiary);
        color: var(--text-primary);
    }
    body.dark-mode .data-table td,
    body.dark-mode .components-table td,
    body.dark-mode .findings-table td {
        border-color: var(--border-light);
        color: var(--text-primary);
    }
    body.dark-mode .findings-table tr:hover,
    body.dark-mode .data-table tr:hover {
        background: var(--bg-tertiary);
    }
    body.dark-mode .findings-wrap,
    body.dark-mode .table-container {
        border-color: var(--border-light);
        background: var(--bg-secondary);
    }
    body.dark-mode .stack-group {
        border-color: var(--border-light);
        background: var(--bg-secondary);
    }
    body.dark-mode .stack-group-header,
    body.dark-mode .stack-header {
        background: var(--bg-tertiary);
        color: var(--text-primary);
    }
    body.dark-mode .stack-group-header:hover,
    body.dark-mode .stack-header:hover {
        background: var(--border-light);
    }
    body.dark-mode .inv-toolbar,
    body.dark-mode .findings-toolbar {
        background: var(--bg-tertiary);
    }
    body.dark-mode .inv-toolbar input,
    body.dark-mode .inv-toolbar select,
    body.dark-mode .findings-toolbar input,
    body.dark-mode .findings-toolbar select {
        background: var(--bg-secondary);
        border-color: var(--border-light);
        color: var(--text-primary);
    }
    body.dark-mode .inv-tab,
    body.dark-mode .report-tab,
    body.dark-mode .nav-link {
        color: var(--text-primary);
    }
    body.dark-mode .view-toggle button {
        background: var(--bg-tertiary);
        border-color: var(--border-light);
        color: var(--text-primary);
    }
    body.dark-mode .message {
        color: var(--text-secondary);
    }
    body.dark-mode .message code {
        background: var(--bg-tertiary);
        color: var(--text-primary);
    }
    body.dark-mode .tool-badge {
        background: var(--bg-tertiary);
        color: #60a5fa;
    }
    body.dark-mode .section-title {
        color: #818cf8;
    }
    body.dark-mode .error {
        background: #2d1b1b;
        color: #fca5a5;
        border-color: var(--severity-critical);
    }
    body.dark-mode .findings-pagination {
        color: var(--text-secondary);
    }
    body.dark-mode .findings-pagination button {
        background: var(--bg-tertiary);
        border-color: var(--border-light);
        color: var(--text-primary);
    }
"""

# =============================================================================
# Semantic color helper functions
# =============================================================================


def get_cost_color(amount: float) -> str:
    """Get CSS variable reference based on cost amount."""
    if amount < 100:
        return "var(--cost-low)"
    elif amount < 500:
        return "var(--cost-medium)"
    elif amount < 1000:
        return "var(--cost-high)"
    else:
        return "var(--cost-critical)"


def get_severity_color(severity: str) -> str:
    """Get CSS variable reference based on severity level."""
    severity_map = {
        "critical": "var(--severity-critical)",
        "high": "var(--severity-high)",
        "medium": "var(--severity-medium)",
        "low": "var(--severity-low)",
        "info": "var(--severity-info)",
    }
    return severity_map.get(severity.lower(), "var(--status-neutral)")


def get_status_color(status: str) -> str:
    """Get CSS variable reference based on status."""
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


def get_full_css() -> str:
    """Get the complete CSS (light + dark mode) as a single injectable string.

    Usage in templates:
        <style>{{ thoth_css }}</style>
    Usage in Python:
        css = get_full_css()
        html = f"<style>{css}</style>"
    """
    return THOTH_COLORS + "\n" + THOTH_DARK_MODE


def get_severity_badge_css() -> str:
    """Get CSS for severity badges (used across scan and findings views)."""
    return """
    .sev-badge, .severity-badge {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 4px 10px; border-radius: var(--radius-pill);
        font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
    }
    .sev-badge.critical, .severity-badge.critical { background: #fef2f2; color: var(--severity-critical); }
    .sev-badge.high, .severity-badge.high { background: #fff1f2; color: var(--severity-high); }
    .sev-badge.medium, .severity-badge.medium { background: #fffbeb; color: var(--severity-medium); }
    .sev-badge.low, .severity-badge.low { background: #f0fdf4; color: #16a34a; }
    .sev-badge.info, .severity-badge.info { background: #eff6ff; color: var(--severity-info); }
    """


# =============================================================================
# Raw hex values (for Python code that needs raw colors, e.g. Rich console)
# =============================================================================
HEX = {
    # Brand
    "primary": "#667eea",
    "secondary": "#764ba2",
    # Status (for backgrounds / UI fills)
    "success": "#10b981",
    "warning": "#f59e0b",
    "error": "#ef4444",
    "info": "#3b82f6",
    "neutral": "#6b7280",
    # Status (WCAG AA text-safe on white)
    "success_text": "#047857",
    "warning_text": "#b45309",
    "error_text": "#dc2626",
    "info_text": "#1d4ed8",
    # Severity (for backgrounds / badges)
    "critical": "#dc2626",
    "high": "#ef4444",
    "medium": "#f59e0b",
    "low": "#fbbf24",
    # Severity (WCAG AA text-safe on white)
    "critical_text": "#991b1b",
    "high_text": "#dc2626",
    "medium_text": "#b45309",
    "low_text": "#a16207",
}
