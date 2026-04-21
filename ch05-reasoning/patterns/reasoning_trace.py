from dataclasses import dataclass


@dataclass
class ReasoningTrace:
    """Observable record of reasoning decisions."""
    query_id: str
    classified_complexity: str  #A
    model_used: str
    thinking_tokens: int = 0
    reasoning_steps: int = 0
    backtracks: int = 0  #B
    hypotheses_generated: int = 0
    hypotheses_refuted: int = 0
    final_confidence: float = 0.0
    wall_time_ms: int = 0

    @property
    def reasoning_efficiency(self) -> float:  #C
        if self.thinking_tokens == 0:
            return 0
        return self.reasoning_steps / (self.thinking_tokens / 1000)

    @property
    def backtrack_rate(self) -> float:  #D
        if self.hypotheses_generated == 0:
            return 0
        return self.hypotheses_refuted / self.hypotheses_generated

    def log(self):
        print(f"  [{self.query_id}] "
              f"complexity={self.classified_complexity} "
              f"model={self.model_used} "
              f"steps={self.reasoning_steps} "
              f"backtracks={self.backtracks} "
              f"confidence={self.final_confidence:.2f} "
              f"efficiency={self.reasoning_efficiency:.2f} "
              f"time={self.wall_time_ms}ms")
