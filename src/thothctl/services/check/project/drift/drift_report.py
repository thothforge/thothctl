"""Report generation for drift detection results."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import DriftResult, DriftSeverity, DriftSummary

logger = logging.getLogger(__name__)

_SEVERITY_ICON = {
    DriftSeverity.CRITICAL: "🔴",
    DriftSeverity.HIGH: "🟠",
    DriftSeverity.MEDIUM: "🟡",
    DriftSeverity.LOW: "🟢",
}


class DriftReportGenerator:
    """Generate drift detection reports in multiple formats."""

    # ------------------------------------------------------------------
    # Console (Rich)
    # ------------------------------------------------------------------

    def display_console(self, summary: DriftSummary, console) -> None:
        """Print drift results using Rich console."""
        from rich.panel import Panel
        from rich.table import Table
        from rich import box

        if not summary.results:
            console.print("[yellow]No stacks analysed.[/yellow]")
            return

        # Summary panel
        status = "[red]DRIFT DETECTED[/red]" if summary.has_drift else "[green]NO DRIFT[/green]"
        console.print(Panel(
            f"Status: {status}\n"
            f"Stacks scanned: {len(summary.results)}\n"
            f"Total resources: {summary.total_resources}\n"
            f"Drifted resources: {summary.total_drifted}\n"
            f"IaC coverage: {summary.overall_coverage}%",
            title="🔍 Drift Detection Summary",
            border_style="red" if summary.has_drift else "green",
        ))

        for result in summary.results:
            if result.error:
                console.print(f"[red]❌ {result.directory}: {result.error}[/red]")
                continue
            if not result.has_drift:
                console.print(f"[green]✅ {result.directory}: no drift ({result.total_resources} resources)[/green]")
                continue

            table = Table(
                title=f"📂 {result.directory}",
                box=box.ROUNDED,
                show_lines=True,
            )
            table.add_column("Severity", width=10)
            table.add_column("Resource", min_width=30)
            table.add_column("Type", min_width=15)
            table.add_column("Drift", width=12)
            table.add_column("Changed Attributes", min_width=20)

            for dr in sorted(result.drifted_resources, key=lambda x: list(DriftSeverity).index(x.severity)):
                sev = dr.severity
                color = {"critical": "red", "high": "orange3", "medium": "yellow", "low": "green"}[sev.value]
                table.add_row(
                    f"[{color}]{_SEVERITY_ICON[sev]} {sev.value.upper()}[/{color}]",
                    dr.address,
                    dr.resource_type,
                    dr.drift_type.value,
                    ", ".join(dr.changed_attributes[:5]) or "-",
                )
            console.print(table)

    # ------------------------------------------------------------------
    # Markdown (for PR comments)
    # ------------------------------------------------------------------

    def generate_markdown(self, summary: DriftSummary) -> str:
        status = "🔴 DRIFT DETECTED" if summary.has_drift else "🟢 NO DRIFT"
        lines = [
            "## 🔍 ThothCTL Drift Detection\n",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Status | {status} |",
            f"| Stacks scanned | {len(summary.results)} |",
            f"| Total resources | {summary.total_resources} |",
            f"| Drifted resources | {summary.total_drifted} |",
            f"| IaC coverage | {summary.overall_coverage}% |",
        ]

        for result in summary.results:
            if result.error:
                lines.append(f"\n### ❌ {result.directory}\nError: `{result.error}`")
                continue
            if not result.has_drift:
                continue

            lines.append(f"\n### 📂 {result.directory}\n")
            lines.append("| Severity | Resource | Drift | Changed |")
            lines.append("|----------|----------|-------|---------|")
            for dr in result.drifted_resources:
                icon = _SEVERITY_ICON[dr.severity]
                attrs = ", ".join(dr.changed_attributes[:3]) or "-"
                lines.append(f"| {icon} {dr.severity.value} | `{dr.address}` | {dr.drift_type.value} | {attrs} |")

        lines.append("\n---")
        lines.append("*Posted by [ThothCTL](https://github.com/thothforge/thothctl)*")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    def generate_json(self, summary: DriftSummary, output_path: Optional[str] = None) -> str:
        data = summary.to_dict()
        data["generated_at"] = datetime.now().isoformat()
        content = json.dumps(data, indent=2)
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(content)
            logger.info(f"JSON report written to {output_path}")
        return content

    # ------------------------------------------------------------------
    # HTML
    # ------------------------------------------------------------------

    def generate_html(self, summary: DriftSummary, output_path: str) -> str:
        sev_rows = ""
        for result in summary.results:
            for dr in result.drifted_resources:
                color = {"critical": "#e74c3c", "high": "#e67e22", "medium": "#f1c40f", "low": "#2ecc71"}[dr.severity.value]
                attrs = ", ".join(dr.changed_attributes[:5]) or "-"
                sev_rows += (
                    f"<tr>"
                    f"<td style='color:{color};font-weight:bold'>{dr.severity.value.upper()}</td>"
                    f"<td>{dr.address}</td>"
                    f"<td>{dr.resource_type}</td>"
                    f"<td>{dr.drift_type.value}</td>"
                    f"<td>{attrs}</td>"
                    f"<td>{result.directory}</td>"
                    f"</tr>\n"
                )

        status_color = "#e74c3c" if summary.has_drift else "#2ecc71"
        status_text = "DRIFT DETECTED" if summary.has_drift else "NO DRIFT"

        html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Drift Detection Report</title>
<style>
body{{font-family:Inter,system-ui,sans-serif;margin:2rem;background:#f8f9fa;color:#333}}
h1{{color:#2c3e50}}
.summary{{display:flex;gap:1rem;flex-wrap:wrap;margin:1.5rem 0}}
.card{{background:#fff;border-radius:8px;padding:1.2rem;min-width:160px;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.card h3{{margin:0 0 .5rem;font-size:.85rem;color:#666}}
.card .value{{font-size:1.6rem;font-weight:700}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
th{{background:#2c3e50;color:#fff;padding:.75rem;text-align:left}}
td{{padding:.65rem .75rem;border-bottom:1px solid #eee}}
tr:hover{{background:#f5f6fa}}
.status{{display:inline-block;padding:.3rem .8rem;border-radius:4px;color:#fff;font-weight:700}}
</style></head><body>
<h1>🔍 Drift Detection Report</h1>
<p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
<div class="summary">
  <div class="card"><h3>Status</h3><div class="value"><span class="status" style="background:{status_color}">{status_text}</span></div></div>
  <div class="card"><h3>Stacks</h3><div class="value">{len(summary.results)}</div></div>
  <div class="card"><h3>Resources</h3><div class="value">{summary.total_resources}</div></div>
  <div class="card"><h3>Drifted</h3><div class="value" style="color:{status_color}">{summary.total_drifted}</div></div>
  <div class="card"><h3>IaC Coverage</h3><div class="value">{summary.overall_coverage}%</div></div>
</div>
{"<h2>Drifted Resources</h2><table><tr><th>Severity</th><th>Resource</th><th>Type</th><th>Drift</th><th>Changed</th><th>Stack</th></tr>" + sev_rows + "</table>" if sev_rows else "<p style='color:#2ecc71;font-size:1.2rem'>✅ No drift detected across all stacks.</p>"}
<footer style="margin-top:2rem;color:#999;font-size:.8rem">Generated by <a href="https://github.com/thothforge/thothctl">ThothCTL</a></footer>
</body></html>"""

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(html)
        logger.info(f"HTML report written to {output_path}")
        return output_path
