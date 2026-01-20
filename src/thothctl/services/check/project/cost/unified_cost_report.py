"""Unified cost analysis report generator matching ThothCTL report standards."""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class UnifiedCostReportGenerator:
    """Generate unified cost analysis reports with stack-based navigation."""
    
    def __init__(self):
        self.reports = []
        
    def add_stack_report(self, stack_name: str, analysis: Any, report_path: Path):
        """Add a stack cost analysis to the unified report."""
        self.reports.append({
            'stack_name': stack_name,
            'analysis': analysis,
            'report_path': report_path,
            'monthly_cost': analysis.total_monthly_cost,
            'annual_cost': analysis.total_annual_cost
        })
    
    def generate_unified_index(self, output_dir: Path, project_name: str = "Infrastructure"):
        """Generate unified index page with all stack reports."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_monthly = sum(r['monthly_cost'] for r in self.reports)
        total_annual = sum(r['annual_cost'] for r in self.reports)
        
        # Sort by cost descending
        sorted_reports = sorted(self.reports, key=lambda x: x['monthly_cost'], reverse=True)
        
        html = self._generate_index_html(
            project_name, timestamp, total_monthly, total_annual, sorted_reports
        )
        
        index_path = output_dir / "index.html"
        with open(index_path, 'w') as f:
            f.write(html)
        
        logger.info(f"Generated unified cost analysis index: {index_path}")
        return index_path
    
    def _generate_index_html(self, project_name: str, timestamp: str, 
                            total_monthly: float, total_annual: float,
                            reports: List[Dict]) -> str:
        """Generate the unified index HTML."""
        
        # Generate stack cards
        stack_cards_html = ""
        for report in reports:
            percentage = (report['monthly_cost'] / total_monthly * 100) if total_monthly > 0 else 0
            stack_cards_html += f"""
            <div class="stack-card" onclick="window.location.href='{report['report_path'].name}'">
                <div class="stack-header">
                    <h3 class="stack-name">🏗️ {report['stack_name']}</h3>
                    <span class="stack-percentage">{percentage:.1f}%</span>
                </div>
                <div class="stack-cost">
                    <div class="cost-monthly">${report['monthly_cost']:,.2f}/month</div>
                    <div class="cost-annual">${report['annual_cost']:,.2f}/year</div>
                </div>
                <div class="stack-bar">
                    <div class="stack-bar-fill" style="width: {percentage}%"></div>
                </div>
                <div class="stack-footer">
                    <span class="view-details">View Details →</span>
                </div>
            </div>
            """
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>💰 Cost Analysis - {project_name}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        {self._get_unified_css()}
    </style>
</head>
<body>
    <div class="container">
        <div class="nav-header">
            <div class="nav-title">💰 AWS Cost Analysis</div>
            <div class="nav-subtitle">{project_name} - Generated on {timestamp}</div>
            <div class="nav-menu">
                <a href="#summary" class="nav-link">📊 Summary</a>
                <a href="#stacks" class="nav-link">🏗️ Stacks</a>
                <a href="#breakdown" class="nav-link">📈 Breakdown</a>
            </div>
        </div>
        
        <div class="content-section" id="summary">
            <div class="section-header">
                <h2 class="section-title">📊 Cost Summary</h2>
            </div>
            <div class="summary-grid">
                <div class="summary-card">
                    <div class="summary-icon">💵</div>
                    <div class="summary-number">${total_monthly:,.2f}</div>
                    <div class="summary-label">Total Monthly Cost</div>
                </div>
                <div class="summary-card">
                    <div class="summary-icon">📅</div>
                    <div class="summary-number">${total_annual:,.2f}</div>
                    <div class="summary-label">Total Annual Cost</div>
                </div>
                <div class="summary-card">
                    <div class="summary-icon">🏗️</div>
                    <div class="summary-number">{len(reports)}</div>
                    <div class="summary-label">Infrastructure Stacks</div>
                </div>
                <div class="summary-card">
                    <div class="summary-icon">📊</div>
                    <div class="summary-number">${total_monthly / len(reports) if reports else 0:,.2f}</div>
                    <div class="summary-label">Average Stack Cost</div>
                </div>
            </div>
        </div>
        
        <div class="content-section" id="stacks">
            <div class="section-header">
                <h2 class="section-title">🏗️ Cost by Stack</h2>
                <span class="section-subtitle">{len(reports)} stacks analyzed</span>
            </div>
            <div class="stacks-grid">
                {stack_cards_html}
            </div>
        </div>
        
        <div class="content-section" id="breakdown">
            <div class="section-header">
                <h2 class="section-title">📈 Cost Breakdown</h2>
            </div>
            <div class="breakdown-table">
                <table>
                    <thead>
                        <tr>
                            <th>Stack</th>
                            <th>Monthly Cost</th>
                            <th>Annual Cost</th>
                            <th>% of Total</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {self._generate_breakdown_rows(reports, total_monthly)}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="footer">
            <p>Generated by ThothCTL Cost Analysis</p>
            <p>Report generated on {timestamp}</p>
        </div>
    </div>
</body>
</html>"""
    
    def _generate_breakdown_rows(self, reports: List[Dict], total: float) -> str:
        """Generate table rows for cost breakdown."""
        rows = ""
        for report in reports:
            percentage = (report['monthly_cost'] / total * 100) if total > 0 else 0
            rows += f"""
                <tr>
                    <td><strong>{report['stack_name']}</strong></td>
                    <td>${report['monthly_cost']:,.2f}</td>
                    <td>${report['annual_cost']:,.2f}</td>
                    <td>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: {percentage}%"></div>
                            <span class="progress-text">{percentage:.1f}%</span>
                        </div>
                    </td>
                    <td>
                        <a href="{report['report_path'].name}" class="btn-view">View Details</a>
                    </td>
                </tr>
            """
        return rows
    
    def _get_unified_css(self) -> str:
        """Get unified CSS matching ThothCTL report standards."""
        return """
        :root {
            --primary-color: #007bff;
            --secondary-color: #6c757d;
            --success-color: #28a745;
            --warning-color: #ffc107;
            --danger-color: #dc3545;
            --info-color: #17a2b8;
            --light-color: #f8f9fa;
            --dark-color: #343a40;
            --border-radius: 8px;
            --box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            --transition: all 0.3s ease;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: var(--dark-color);
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: var(--border-radius);
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .nav-header {
            background: linear-gradient(135deg, var(--primary-color), #0056b3);
            color: white;
            padding: 30px 40px;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .nav-title {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 8px;
        }
        
        .nav-subtitle {
            font-size: 1rem;
            opacity: 0.9;
            margin-bottom: 20px;
        }
        
        .nav-menu {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        
        .nav-link {
            color: rgba(255,255,255,0.9);
            text-decoration: none;
            padding: 8px 20px;
            border-radius: 20px;
            transition: var(--transition);
            font-weight: 500;
            font-size: 0.95rem;
        }
        
        .nav-link:hover {
            background: rgba(255,255,255,0.2);
            color: white;
            transform: translateY(-1px);
        }
        
        .content-section {
            padding: 40px;
            border-bottom: 1px solid #e9ecef;
        }
        
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 3px solid var(--primary-color);
        }
        
        .section-title {
            font-size: 1.8rem;
            font-weight: 600;
            color: var(--primary-color);
        }
        
        .section-subtitle {
            color: var(--secondary-color);
            font-size: 0.95rem;
        }
        
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 25px;
            margin-bottom: 20px;
        }
        
        .summary-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: var(--border-radius);
            box-shadow: var(--box-shadow);
            text-align: center;
            transition: var(--transition);
        }
        
        .summary-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
        }
        
        .summary-icon {
            font-size: 2.5rem;
            margin-bottom: 10px;
        }
        
        .summary-number {
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 8px;
        }
        
        .summary-label {
            font-size: 0.95rem;
            opacity: 0.9;
        }
        
        .stacks-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 25px;
        }
        
        .stack-card {
            background: white;
            border: 2px solid #e9ecef;
            border-radius: var(--border-radius);
            padding: 25px;
            cursor: pointer;
            transition: var(--transition);
        }
        
        .stack-card:hover {
            border-color: var(--primary-color);
            box-shadow: 0 8px 16px rgba(0,0,0,0.1);
            transform: translateY(-3px);
        }
        
        .stack-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .stack-name {
            font-size: 1.3rem;
            font-weight: 600;
            color: var(--dark-color);
        }
        
        .stack-percentage {
            background: var(--primary-color);
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.9rem;
            font-weight: 600;
        }
        
        .stack-cost {
            margin-bottom: 15px;
        }
        
        .cost-monthly {
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--primary-color);
            margin-bottom: 5px;
        }
        
        .cost-annual {
            font-size: 1rem;
            color: var(--secondary-color);
        }
        
        .stack-bar {
            height: 8px;
            background: #e9ecef;
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 15px;
        }
        
        .stack-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary-color), var(--info-color));
            transition: width 0.5s ease;
        }
        
        .stack-footer {
            text-align: right;
        }
        
        .view-details {
            color: var(--primary-color);
            font-weight: 500;
            font-size: 0.95rem;
        }
        
        .breakdown-table {
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
        }
        
        th {
            background: var(--primary-color);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }
        
        td {
            padding: 15px;
            border-bottom: 1px solid #e9ecef;
        }
        
        tr:hover {
            background: var(--light-color);
        }
        
        .progress-bar {
            position: relative;
            height: 25px;
            background: #e9ecef;
            border-radius: 12px;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary-color), var(--info-color));
            transition: width 0.5s ease;
        }
        
        .progress-text {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-weight: 600;
            font-size: 0.85rem;
            color: var(--dark-color);
        }
        
        .btn-view {
            display: inline-block;
            padding: 8px 20px;
            background: var(--primary-color);
            color: white;
            text-decoration: none;
            border-radius: 20px;
            font-weight: 500;
            font-size: 0.9rem;
            transition: var(--transition);
        }
        
        .btn-view:hover {
            background: #0056b3;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        
        .footer {
            text-align: center;
            padding: 30px;
            background: var(--light-color);
            color: var(--secondary-color);
            font-size: 0.9rem;
        }
        
        .footer p {
            margin: 5px 0;
        }
        
        @media print {
            body {
                background: white;
                padding: 0;
            }
            .container {
                box-shadow: none;
            }
            .nav-header {
                position: static;
            }
            .stack-card {
                break-inside: avoid;
            }
        }
        
        @media (max-width: 768px) {
            .summary-grid {
                grid-template-columns: 1fr;
            }
            .stacks-grid {
                grid-template-columns: 1fr;
            }
            .nav-menu {
                flex-direction: column;
                gap: 10px;
            }
        }
        """
