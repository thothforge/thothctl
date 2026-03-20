"""Cost tracking for AI provider usage."""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

COST_LOG_DIR = ".thothctl/ai_costs"

# Approximate cost per 1K tokens (input/output)
TOKEN_COSTS = {
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "anthropic.claude-3-sonnet-20240229-v1:0": {"input": 0.003, "output": 0.015},
    "anthropic.claude-3-haiku-20240307-v1:0": {"input": 0.00025, "output": 0.00125},
}

# Ollama / local models are free — any model not in TOKEN_COSTS defaults to
# the fallback in _calculate_cost, so we add a zero-cost entry prefix-matched
# in the method below.
OLLAMA_COST = {"input": 0.0, "output": 0.0}


@dataclass
class UsageRecord:
    """Single API usage record."""
    timestamp: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    operation: str = ""


@dataclass
class CostTracker:
    """Tracks AI API usage and costs."""
    daily_limit: float = 100.0
    monthly_budget: float = 200.0
    _records: List[UsageRecord] = field(default_factory=list)

    def record_usage(self, provider: str, model: str, input_tokens: int,
                     output_tokens: int, operation: str = "") -> float:
        """Record a usage event and return the cost."""
        cost = self._calculate_cost(model, input_tokens, output_tokens, provider)
        record = UsageRecord(
            timestamp=datetime.utcnow().isoformat(),
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            operation=operation,
        )
        self._records.append(record)
        self._persist_record(record)
        return cost

    def get_daily_spend(self) -> float:
        """Get total spend for today."""
        today = date.today().isoformat()
        return sum(r.cost for r in self._records if r.timestamp.startswith(today))

    def get_monthly_spend(self) -> float:
        """Get total spend for current month."""
        month_prefix = date.today().strftime("%Y-%m")
        return sum(r.cost for r in self._records if r.timestamp.startswith(month_prefix))

    def check_budget(self) -> bool:
        """Return True if within budget limits."""
        if self.get_daily_spend() >= self.daily_limit:
            logger.warning("Daily AI spending limit reached")
            return False
        if self.get_monthly_spend() >= self.monthly_budget:
            logger.warning("Monthly AI budget exceeded")
            return False
        return True

    def get_cost_report(self, period: str = "daily") -> Dict:
        """Generate a cost report for the given period."""
        today = date.today()
        if period == "daily":
            prefix = today.isoformat()
        elif period == "weekly":
            week_start = today.isoformat()  # simplified
            prefix = today.strftime("%Y-%m")
        else:
            prefix = today.strftime("%Y-%m")

        filtered = [r for r in self._records if r.timestamp.startswith(prefix)]
        by_provider: Dict[str, float] = {}
        by_model: Dict[str, float] = {}
        for r in filtered:
            by_provider[r.provider] = by_provider.get(r.provider, 0) + r.cost
            by_model[r.model] = by_model.get(r.model, 0) + r.cost

        return {
            "period": period,
            "total_cost": sum(r.cost for r in filtered),
            "total_requests": len(filtered),
            "total_input_tokens": sum(r.input_tokens for r in filtered),
            "total_output_tokens": sum(r.output_tokens for r in filtered),
            "by_provider": by_provider,
            "by_model": by_model,
        }

    @staticmethod
    def _calculate_cost(model: str, input_tokens: int, output_tokens: int,
                        provider: str = "") -> float:
        if provider == "ollama":
            return 0.0
        costs = TOKEN_COSTS.get(model, {"input": 0.01, "output": 0.03})
        return (input_tokens / 1000 * costs["input"]) + (output_tokens / 1000 * costs["output"])

    def _persist_record(self, record: UsageRecord) -> None:
        """Append record to daily log file."""
        try:
            log_dir = Path(COST_LOG_DIR)
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{date.today().isoformat()}.jsonl"
            with open(log_file, "a") as f:
                f.write(json.dumps(vars(record)) + "\n")
        except Exception as e:
            logger.debug(f"Failed to persist cost record: {e}")

    def load_records(self) -> None:
        """Load records from disk for current month."""
        log_dir = Path(COST_LOG_DIR)
        if not log_dir.exists():
            return
        month_prefix = date.today().strftime("%Y-%m")
        for log_file in log_dir.glob(f"{month_prefix}*.jsonl"):
            try:
                with open(log_file) as f:
                    for line in f:
                        data = json.loads(line.strip())
                        self._records.append(UsageRecord(**data))
            except Exception as e:
                logger.debug(f"Failed to load cost records from {log_file}: {e}")
