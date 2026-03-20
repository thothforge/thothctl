"""Safety controls: confidence checking, rate limiting, and emergency overrides."""
import json
import logging
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Tuple, Dict, List, Optional

from ..config.decision_rules import SafetyConfig

logger = logging.getLogger(__name__)

ACTIONS_LOG_DIR = ".thothctl/ai_decisions"


@dataclass
class ActionRecord:
    timestamp: float
    action: str
    repository: str
    pr_id: str
    confidence: float
    reason: str


class SafetyGuard:
    """Unified safety controls for auto-decisions."""

    def __init__(self, config: SafetyConfig):
        self.config = config
        self._today_actions: List[ActionRecord] = []
        self._load_today_actions()

    # -- Confidence --

    def check_confidence(self, action: str, confidence: float) -> Tuple[bool, str]:
        """Check if confidence meets threshold for the given action."""
        thresholds = {
            "approve": 0.90,
            "reject": 0.85,
            "request_changes": 0.80,
        }
        required = thresholds.get(action, 0.95)
        if confidence >= required:
            return True, f"Confidence {confidence:.0%} meets threshold {required:.0%}"
        return False, f"Confidence {confidence:.0%} below threshold {required:.0%}. Manual review required."

    # -- Rate limiting --

    def check_rate_limit(self, action: str, repository: str) -> Tuple[bool, str]:
        """Check if action is within daily rate limits and cooldown."""
        # Daily limit
        limit_key = f"max_auto_{action}s_per_day" if action != "request_changes" else "max_auto_approvals_per_day"
        daily_limit = getattr(self.config, limit_key, 50)
        daily_count = sum(1 for a in self._today_actions if a.action == action and a.repository == repository)

        if daily_count >= daily_limit:
            return False, f"Daily limit of {daily_limit} {action}s reached for {repository}"

        # Cooldown
        repo_actions = [a for a in self._today_actions if a.repository == repository]
        if repo_actions:
            last = max(a.timestamp for a in repo_actions)
            elapsed = time.time() - last
            if elapsed < self.config.cooldown_between_actions:
                remaining = self.config.cooldown_between_actions - elapsed
                return False, f"Cooldown: {remaining:.0f}s remaining"

        return True, "Within rate limits"

    # -- Override --

    def check_override(self, pr_context: Dict) -> Tuple[bool, str]:
        """Check if PR qualifies for emergency override (skip auto-decision)."""
        labels = pr_context.get("labels", [])
        author = pr_context.get("author", "")
        approvers = pr_context.get("approvers", [])

        if any(label in self.config.emergency_labels for label in labels):
            return True, f"Emergency label detected: {set(labels) & set(self.config.emergency_labels)}"
        if author in self.config.trusted_bots:
            return True, f"Trusted bot: {author}"
        if any(a in self.config.bypass_approvers for a in approvers):
            return True, "Bypass approver present"

        return False, "No override conditions met"

    # -- Full check --

    def can_take_action(self, action: str, confidence: float,
                        repository: str, pr_context: Optional[Dict] = None) -> Tuple[bool, str]:
        """Run all safety checks. Returns (allowed, reason)."""
        # Override check first
        if pr_context:
            overridden, reason = self.check_override(pr_context)
            if overridden:
                return False, f"Override active: {reason}. Falling back to comment-only."

        ok, reason = self.check_confidence(action, confidence)
        if not ok:
            return False, reason

        ok, reason = self.check_rate_limit(action, repository)
        if not ok:
            return False, reason

        return True, "All safety checks passed"

    # -- Recording --

    def record_action(self, action: str, repository: str, pr_id: str,
                      confidence: float, reason: str) -> None:
        record = ActionRecord(
            timestamp=time.time(), action=action, repository=repository,
            pr_id=pr_id, confidence=confidence, reason=reason,
        )
        self._today_actions.append(record)
        self._persist_record(record)

    def get_today_stats(self) -> Dict:
        actions = {}
        for a in self._today_actions:
            actions[a.action] = actions.get(a.action, 0) + 1
        return {"date": date.today().isoformat(), "actions": actions, "total": len(self._today_actions)}

    # -- Persistence --

    def _persist_record(self, record: ActionRecord) -> None:
        try:
            log_dir = Path(ACTIONS_LOG_DIR)
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{date.today().isoformat()}.jsonl"
            with open(log_file, "a") as f:
                f.write(json.dumps(vars(record)) + "\n")
        except Exception as e:
            logger.debug(f"Failed to persist action record: {e}")

    def _load_today_actions(self) -> None:
        log_file = Path(ACTIONS_LOG_DIR) / f"{date.today().isoformat()}.jsonl"
        if not log_file.exists():
            return
        try:
            with open(log_file) as f:
                for line in f:
                    self._today_actions.append(ActionRecord(**json.loads(line.strip())))
        except Exception as e:
            logger.debug(f"Failed to load action records: {e}")
