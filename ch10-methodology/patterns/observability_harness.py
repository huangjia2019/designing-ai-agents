import time
import json
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Span:
    """A single unit of agent work."""
    name: str
    span_type: str
    start_time: float = field(
        default_factory=time.time
    )
    end_time: float | None = None
    metadata: dict = field(
        default_factory=dict
    )
    children: list["Span"] = field(
        default_factory=list
    )

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return 0
        return (
            (self.end_time - self.start_time)
            * 1000
        )

    def finish(self, **extra_metadata):
        self.end_time = time.time()
        self.metadata.update(extra_metadata)


class AgentObserver:
    """Observability layer for agent systems.

    Implements the Observability Harness
    (Governance × Orchestrate). Central
    coordinator receiving signals from all
    components and aggregating them.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.traces: list[list[Span]] = []
        self.current_trace: list[Span] = []
        self.metrics: dict = defaultdict(list)

    def start_trace(
        self, task_description: str
    ):
        """Begin a new trace for a task."""
        self.current_trace = []
        self.traces.append(self.current_trace)
        self.start_span(
            "task", "task",
            description=task_description,
        )

    def start_span(
        self, name: str, span_type: str,
        **metadata,
    ) -> Span:
        """Start a span within current trace."""
        span = Span(
            name=name, span_type=span_type,
            metadata=metadata,
        )
        self.current_trace.append(span)
        return span

    def record_llm_call(
        self, model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        duration_ms: float,
    ):
        """Record an LLM API call."""
        span = Span(
            name=f"llm:{model}",
            span_type="llm_call",
            metadata={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
            },
        )
        span.end_time = (
            span.start_time
            + (duration_ms / 1000)
        )
        self.current_trace.append(span)

        self.metrics["total_tokens"].append(
            input_tokens + output_tokens
        )
        self.metrics["total_cost"].append(
            cost_usd
        )
        self.metrics["llm_latency_ms"].append(
            duration_ms
        )

    def record_tool_call(
        self, tool_name: str,
        success: bool,
        duration_ms: float,
    ):
        """Record a tool invocation."""
        span = Span(
            name=f"tool:{tool_name}",
            span_type="tool_call",
            metadata={"success": success},
        )
        span.end_time = (
            span.start_time
            + (duration_ms / 1000)
        )
        self.current_trace.append(span)

        self.metrics["tool_calls"].append(
            tool_name
        )
        self.metrics["tool_success"].append(
            1 if success else 0
        )

    def record_task_outcome(
        self, success: bool,
        human_override: bool,
    ):
        """Record the final task outcome."""
        self.metrics["task_success"].append(
            1 if success else 0
        )
        self.metrics["human_override"].append(
            1 if human_override else 0
        )

    def get_dashboard(self) -> dict:
        """Summary dashboard of key metrics."""
        def safe_avg(lst):
            return (
                sum(lst) / len(lst)
                if lst else 0
            )

        tasks = self.metrics["task_success"]
        overrides = self.metrics[
            "human_override"
        ]
        tools = self.metrics["tool_success"]

        return {
            "agent_id": self.agent_id,
            "total_traces": len(self.traces),
            "task_success_rate":
                f"{safe_avg(tasks):.1%}",
            "human_override_rate":
                f"{safe_avg(overrides):.1%}",
            "tool_success_rate":
                f"{safe_avg(tools):.1%}",
            "total_cost_usd":
                f"${sum(self.metrics['total_cost']):.2f}",
            "avg_tokens_per_task": int(
                safe_avg(
                    self.metrics["total_tokens"]
                )
            ),
        }

    def export_traces(self) -> str:
        """Export traces as JSON."""
        export = []
        for trace in self.traces:
            export.append([{
                "name": s.name,
                "type": s.span_type,
                "duration_ms": s.duration_ms,
                "metadata": s.metadata,
            } for s in trace])
        return json.dumps(export, indent=2)
