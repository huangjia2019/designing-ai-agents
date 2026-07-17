from dataclasses import dataclass, field
from enum import IntEnum


class TrustLevel(IntEnum):
    OBSERVE = 0      # Suggest only
    ASSIST = 1       # Read and analyze
    SUPERVISED = 2   # Execute with approval
    AUTONOMOUS = 3   # Execute independently
    DELEGATED = 4    # Full autonomy


@dataclass
class TrustMetrics:
    """Track performance for trust escalation."""
    total_actions: int = 0
    successful_actions: int = 0
    user_overrides: int = 0
    escalations: int = 0
    errors: int = 0
    consecutive_successes: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_actions == 0:
            return 0.0
        return (
            self.successful_actions
            / self.total_actions
        )

    @property
    def override_rate(self) -> float:
        if self.total_actions == 0:
            return 0.0
        return (
            self.user_overrides
            / self.total_actions
        )


@dataclass
class EscalationThresholds:
    """Thresholds for trust level transitions."""
    min_actions: int = 50
    min_success_rate: float = 0.95
    max_override_rate: float = 0.05
    max_error_rate: float = 0.02
    consecutive_errors_for_demotion: int = 3

class TrustManager:
    """Manage progressive trust escalation
    and demotion.

    Implements Progressive Commitment
    (Governance × Chain): commitment is
    staged — within-session probe checks
    first, then cross-session trust
    escalation.
    """

    def __init__(
        self,
        thresholds: (
            EscalationThresholds | None
        ) = None,
        initial_level: (
            TrustLevel
        ) = TrustLevel.OBSERVE,
    ):
        self.level = initial_level
        self.thresholds = (
            thresholds or EscalationThresholds()
        )
        self.metrics = TrustMetrics()
        self.level_history: list[
            tuple[TrustLevel, str]
        ] = [(initial_level, "initialized")]

    def record_action(
        self, success: bool,
        user_override: bool = False,
    ):
        """Record outcome; check for changes."""
        self.metrics.total_actions += 1

        if success:
            self.metrics.successful_actions += 1
            self.metrics.consecutive_successes += 1
        else:
            self.metrics.errors += 1
            self.metrics.consecutive_successes = 0

        if user_override:
            self.metrics.user_overrides += 1

        # Check for demotion
        thresh = self.thresholds
        if (
            self.metrics.errors
            >= thresh.consecutive_errors_for_demotion
        ):
            self._demote(
                "Consecutive error threshold"
            )

        # Check for escalation
        self._check_escalation()

    def _check_escalation(self):
        if self.level >= TrustLevel.DELEGATED:
            return

        t = self.thresholds
        m = self.metrics

        if (
            m.total_actions >= t.min_actions
            and m.success_rate
            >= t.min_success_rate
            and m.override_rate
            <= t.max_override_rate
        ):
            self._escalate(
                "Performance thresholds met"
            )

    def _escalate(self, reason: str):
        new_level = TrustLevel(
            min(
                self.level + 1,
                TrustLevel.DELEGATED,
            )
        )
        if new_level != self.level:
            self.level = new_level
            self.level_history.append(
                (new_level,
                 f"escalated: {reason}")
            )
            self.metrics = TrustMetrics()

    def _demote(self, reason: str):
        new_level = TrustLevel(
            max(
                self.level - 1,
                TrustLevel.OBSERVE,
            )
        )
        if new_level != self.level:
            self.level = new_level
            self.level_history.append(
                (new_level,
                 f"demoted: {reason}")
            )
            self.metrics = TrustMetrics()

    def should_ask_human(
        self, risk_level: str
    ) -> bool:
        """Determine if action needs approval."""
        if self.level <= TrustLevel.OBSERVE:
            return True
        if self.level == TrustLevel.ASSIST:
            return True
        if self.level == TrustLevel.SUPERVISED:
            return risk_level in (
                "high", "critical"
            )
        if self.level == TrustLevel.AUTONOMOUS:
            return risk_level == "critical"
        return False  # DELEGATED: audit only

    def get_status(self) -> dict:
        return {
            "level": self.level.name,
            "metrics": {
                "total":
                    self.metrics.total_actions,
                "success_rate":
                    f"{self.metrics.success_rate:.1%}",
                "override_rate":
                    f"{self.metrics.override_rate:.1%}",
            },
            "history_length":
                len(self.level_history),
        }
