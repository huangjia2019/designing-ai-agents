"""Telemetry skeleton for reasoning-policy decisions."""

from dataclasses import dataclass


@dataclass
class ReasoningTrace:
    """Observable record of one routed reasoning decision."""

    query_id: str
    classified_complexity: str
    model_used: str
    output_tokens: int = 0
    reasoning_steps: int = 0
    backtracks: int = 0
    hypotheses_generated: int = 0
    hypotheses_refuted: int = 0
    final_confidence: float = 0.0
    wall_time_ms: int = 0

    @property
    def steps_per_1k_output_tokens(self) -> float:
        if self.output_tokens == 0:
            return 0.0
        return self.reasoning_steps / (self.output_tokens / 1000)

    @property
    def reasoning_efficiency(self) -> float:
        """Backward-compatible alias for the earlier demo property."""
        return self.steps_per_1k_output_tokens

    @property
    def hypothesis_refutation_rate(self) -> float:
        if self.hypotheses_generated == 0:
            return 0.0
        return self.hypotheses_refuted / self.hypotheses_generated

    def log(self) -> None:
        print(
            f"  [{self.query_id}] "
            f"complexity={self.classified_complexity} "
            f"model={self.model_used} "
            f"steps={self.reasoning_steps} "
            f"backtracks={self.backtracks} "
            f"confidence={self.final_confidence:.2f} "
            f"steps_per_1k={self.steps_per_1k_output_tokens:.2f} "
            f"time={self.wall_time_ms}ms"
        )
