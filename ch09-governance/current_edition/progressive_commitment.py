"""Listings 9.8–9.11: evidence-based promotion and demotion of trust."""

from dataclasses import dataclass
from enum import IntEnum

class TrustLevel(IntEnum):
    OBSERVE = 0
    ASSIST = 1
    SUPERVISED = 2
    AUTONOMOUS = 3
    DELEGATED = 4

@dataclass
class TrustMetrics:
    total_actions: int = 0
    successful_actions: int = 0
    user_overrides: int = 0
    errors: int = 0
    consecutive_errors: int = 0

    @property
    def success_rate(self) -> float:
        return (
            self.successful_actions / self.total_actions
            if self.total_actions else 0.0
        )

    @property
    def override_rate(self) -> float:
        return (
            self.user_overrides / self.total_actions
            if self.total_actions else 0.0
        )

    @property
    def error_rate(self) -> float:
        return (
            self.errors / self.total_actions
            if self.total_actions
            else 0.0
        )

@dataclass
class EscalationThresholds:
    min_actions: int = 50
    min_success_rate: float = 0.95
    max_override_rate: float = 0.05
    max_error_rate: float = 0.02
    consecutive_errors_for_demotion: int = 3
class TrustManager:
    """Manage evidence-based trust promotion and demotion."""

    def __init__(
        self,
        thresholds: EscalationThresholds | None = None,
        initial_level: TrustLevel = TrustLevel.OBSERVE,
    ):
        self.level = initial_level
        self.thresholds = thresholds or EscalationThresholds()
        self.metrics = TrustMetrics()
        self.level_history = [(initial_level, "initialized")]

    def record_action(
        self, success: bool, user_override: bool = False,
    ):
        self.metrics.total_actions += 1
        if success:
            self.metrics.successful_actions += 1
            self.metrics.consecutive_errors = 0
        else:
            self.metrics.errors += 1
            self.metrics.consecutive_errors += 1
        if user_override:
            self.metrics.user_overrides += 1

        if (
            self.metrics.consecutive_errors
            >= self.thresholds.consecutive_errors_for_demotion
        ):
            return self._demote("Consecutive error threshold")
        self._check_escalation()
    def _check_escalation(self):
        if self.level >= TrustLevel.DELEGATED:
            return
        t, m = self.thresholds, self.metrics
        if (
            m.total_actions >= t.min_actions
            and m.success_rate >= t.min_success_rate
            and m.override_rate <= t.max_override_rate
            and m.error_rate <= t.max_error_rate
        ):
            self._escalate("Performance thresholds met")

    def _escalate(self, reason: str):
        new_level = TrustLevel(min(self.level + 1, TrustLevel.DELEGATED))
        if new_level != self.level:
            self.level = new_level
            self.level_history.append((new_level, f"escalated: {reason}"))
            self.metrics = TrustMetrics()

    def _demote(self, reason: str):
        new_level = TrustLevel(max(self.level - 1, TrustLevel.OBSERVE))
        if new_level != self.level:
            self.level = new_level
            self.level_history.append((new_level, f"demoted: {reason}"))
        self.metrics = TrustMetrics()
    def should_ask_human(
        self, risk_level: str,
        sovereignty_trigger: bool = False,
    ) -> bool:
        if (
            sovereignty_trigger or risk_level == "critical"
        ):
            return True
        if self.level <= TrustLevel.ASSIST:
            return True
        if self.level == TrustLevel.SUPERVISED:
            return risk_level == "high"
        return False

    def get_status(self) -> dict:
        return {
            "level": self.level.name,
            "metrics": {
                "total": self.metrics.total_actions,
                "success_rate": f"{self.metrics.success_rate:.1%}",
                "override_rate": f"{self.metrics.override_rate:.1%}",
                "error_rate": f"{self.metrics.error_rate:.1%}",
            },
            "history_length": len(self.level_history),
        }
