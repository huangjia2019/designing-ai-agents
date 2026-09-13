"""Listings 9.12–9.15: task traces and protected evidence references."""

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from copy import deepcopy

@dataclass
class Span:
    name: str
    span_type: str
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return (
            (self.end_time - self.start_time) * 1000
            if self.end_time is not None else 0
        )

    def finish(self, **metadata):
        self.end_time = time.time()
        self.metadata.update(metadata)

class AgentObserver:
    """A flat teaching trace with explicit task lifecycle."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.traces: list[list[Span]] = []
        self.current_trace: list[Span] = []
        self.current_root: Span | None = None
        self.current_task_tokens = 0
        self.metrics: dict = defaultdict(list)

    def start_trace(self, task_description: str):
        self.current_trace = []
        self.current_task_tokens = 0
        self.traces.append(self.current_trace)
        self.current_root = self.start_span(
            "task", "task", description=task_description
        )

    def finish_trace(self, **metadata):
        if self.current_root is not None:
            self.current_root.finish(**metadata)
            self.current_root = None

    def start_span(self, name: str, span_type: str, **metadata) -> Span:
        span = Span(name=name, span_type=span_type, metadata=metadata)
        self.current_trace.append(span)
        return span
    def record_llm_call(
        self, model: str,
        input_tokens: int, output_tokens: int,
        cost_usd: float, duration_ms: float,
        messages_ref: str | None = None,
        output_ref: str | None = None,
    ):
        span = Span(
            name=f"llm:{model}", span_type="llm_call",
            metadata={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
                "messages_ref": messages_ref,
                "output_ref": output_ref,
            },
        )
        span.end_time = span.start_time + duration_ms / 1000
        self.current_trace.append(span)
        tokens = input_tokens + output_tokens
        self.current_task_tokens += tokens
        self.metrics["total_cost"].append(cost_usd)
        self.metrics["llm_latency_ms"].append(duration_ms)
    def record_decision(
        self, tool_name: str, decision: str, reason: str,
        evidence_ref: str | None = None,
        context: dict | None = None,
    ):
        span = Span(
            name=f"decision:{tool_name}", span_type="decision",
            metadata={
                "decision": decision, "reason": reason,
                "evidence_ref": evidence_ref,
                "context": deepcopy(context or {}),
            },
        )
        span.finish()
        self.current_trace.append(span)

    def record_tool_call(
        self, tool_name: str, success: bool, duration_ms: float,
    ):
        span = Span(
            name=f"tool:{tool_name}", span_type="tool_call",
            metadata={"success": success},
        )
        span.end_time = span.start_time + duration_ms / 1000
        self.current_trace.append(span)
        self.metrics["tool_success"].append(1 if success else 0)

    def record_task_outcome(self, success: bool, human_override: bool):
        span = Span(
            name="task_outcome", span_type="task_outcome",
            metadata={"success": success, "human_override": human_override},
        )
        span.finish()
        self.current_trace.append(span)
        self.metrics["task_success"].append(
            1 if success else 0
        )
        self.metrics["human_override"].append(
            1 if human_override else 0
        )
        self.metrics["tokens_per_task"].append(
            self.current_task_tokens
        )
        self.current_task_tokens = 0
    def get_dashboard(self) -> dict:
        def safe_avg(values):
            return sum(values) / len(values) if values else 0

        return {
            "agent_id": self.agent_id,
            "total_traces": len(self.traces),
            "task_success_rate":
                f"{safe_avg(self.metrics['task_success']):.1%}",
            "human_override_rate":
                f"{safe_avg(self.metrics['human_override']):.1%}",
            "tool_success_rate":
                f"{safe_avg(self.metrics['tool_success']):.1%}",
            "total_cost_usd":
                f"${sum(self.metrics['total_cost']):.2f}",
            "avg_tokens_per_task": int(
                safe_avg(self.metrics["tokens_per_task"])
            ),
        }

    def export_traces(self) -> str:
        """Export teaching JSON; this is not OTLP."""
        return json.dumps([
            [{
                "name": span.name,
                "type": span.span_type,
                "duration_ms": span.duration_ms,
                "metadata": span.metadata,
            } for span in trace]
            for trace in self.traces
        ], indent=2)
