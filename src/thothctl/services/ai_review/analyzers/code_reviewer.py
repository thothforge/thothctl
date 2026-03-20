"""Code reviewer - analyzes IaC code changes."""
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# File extensions to analyze
IAC_EXTENSIONS = {".tf", ".hcl", ".tfvars", ".yaml", ".yml", ".json"}


class CodeReviewer:
    """Analyzes IaC code files for AI-powered review."""

    def collect_code_for_review(self, directory: str, extensions: set = None) -> Dict[str, str]:
        """Collect IaC files from a directory for review."""
        exts = extensions or IAC_EXTENSIONS
        files: Dict[str, str] = {}
        dir_path = Path(directory)

        if not dir_path.exists():
            logger.warning(f"Directory not found: {directory}")
            return files

        for f in dir_path.rglob("*"):
            if f.suffix in exts and not any(p.startswith(".") for p in f.parts):
                try:
                    content = f.read_text(errors="ignore")
                    rel_path = str(f.relative_to(dir_path))
                    files[rel_path] = content
                except Exception as e:
                    logger.debug(f"Error reading {f}: {e}")

        return files

    def format_for_ai(self, code_files: Dict[str, str], max_chars: int = 50000) -> str:
        """Format collected code files into a string for AI review."""
        lines = [f"Total files to review: {len(code_files)}\n"]
        total = 0

        for path, content in sorted(code_files.items()):
            header = f"\n--- File: {path} ---\n"
            if total + len(header) + len(content) > max_chars:
                lines.append(f"\n[Truncated: {len(code_files) - len(lines) + 1} files omitted due to size]")
                break
            lines.append(header)
            lines.append(content)
            total += len(header) + len(content)

        return "\n".join(lines)
