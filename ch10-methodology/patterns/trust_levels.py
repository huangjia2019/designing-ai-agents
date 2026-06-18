"""Trust Levels — progressive trust as runtime promotion/demotion.

Levels (from Ch2 §2.5):
  Level 0 Suggest          — drafts recommendations, human approves each action
  Level 1 Act-then-review  — executes reversible actions, reviews irreversible
  Level 2 Act-within-bounds — full autonomy inside a defined safe zone
  Level 3 Full autonomy    — execute any available action

Promotions earned by clean trace history; demotions triggered by any
guardrail-blocked or post-check-failed action.
"""
from dataclasses import dataclass
from enum import IntEnum


class TrustLevel(IntEnum):
    SUGGEST = 0
    ACT_THEN_REVIEW = 1
    ACT_WITHIN_BOUNDS = 2
    FULL_AUTONOMY = 3


@dataclass
class TrustState:
    agent: str
    level: TrustLevel = TrustLevel.SUGGEST
    successful_actions: int = 0
    blocked_actions: int = 0
    failed_actions: int = 0

    def credit(self, n: int = 1) -> None:
        self.successful_actions += n

    def debit_block(self, n: int = 1) -> None:
        self.blocked_actions += n

    def debit_fail(self, n: int = 1) -> None:
        self.failed_actions += n


class TrustEngine:
    """Decides promotion/demotion based on action history."""

    PROMOTE_THRESHOLD = 20   # clean actions to earn one level
    DEMOTE_THRESHOLD = 3     # blocked/failed to lose a level

    def __init__(self):
        self.states: dict[str, TrustState] = {}

    def register(self, agent: str, initial: TrustLevel = TrustLevel.SUGGEST) -> None:
        self.states[agent] = TrustState(agent=agent, level=initial)

    def update(self, agent: str, *, success: int = 0,
               blocked: int = 0, failed: int = 0) -> tuple[TrustLevel, str]:
        state = self.states.setdefault(agent, TrustState(agent=agent))
        state.credit(success)
        state.debit_block(blocked)
        state.debit_fail(failed)
        # Demote first (incidents matter more than streaks)
        if (state.blocked_actions + state.failed_actions) >= self.DEMOTE_THRESHOLD:
            if state.level > TrustLevel.SUGGEST:
                state.level = TrustLevel(state.level - 1)
                state.blocked_actions = state.failed_actions = 0
                state.successful_actions = 0
                return state.level, "demoted"
        # Promote on clean streak
        if state.successful_actions >= self.PROMOTE_THRESHOLD:
            if state.level < TrustLevel.FULL_AUTONOMY:
                state.level = TrustLevel(state.level + 1)
                state.successful_actions = 0
                return state.level, "promoted"
        return state.level, "unchanged"
