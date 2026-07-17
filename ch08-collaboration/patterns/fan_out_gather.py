"""Fan-Out/Gather — Collaboration x Parallel.

Independent subtasks go to parallel workers; a coordinated merge step
reconciles their results. Distributing is easy — the merge is where the
design lives or dies.

Listing 8.4 — WorkerTask schema + decompose
Listing 8.5 — parallel execution (_execute_worker, fan_out)
Listing 8.6 — aggregation strategies (gather)
Listing 8.7 — full pipeline (execute)
"""
import concurrent.futures
from dataclasses import dataclass, field
# anthropic is lazy-imported inside functions that need a live client
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = object  # type: ignore[misc,assignment]


@dataclass
class WorkerTask:
    id: str
    description: str
    role: str               # Worker specialization
    model: str = "claude-sonnet-4-6"
    result: str = ""
    status: str = "pending"


class FanOutGather:
    def __init__(
        self,
        client: Anthropic,
        agg_model: str = "claude-sonnet-4-6",
    ):
        self.client = client
        self.aggregator_model = agg_model

    def decompose(
        self,
        goal: str,
        perspectives: list[str],
    ) -> list[WorkerTask]:
        return [
            WorkerTask(
                id=f"W{i+1}",
                description=(
                    f"Analyze from {p} "
                    f"perspective: {goal}"
                ),
                role=(
                    f"You are an expert in {p}. "
                    f"Focus exclusively on "
                    f"{p} concerns."
                ),
            )
            for i, p in enumerate(perspectives)
        ]

    def _execute_worker(
        self, task: WorkerTask
    ) -> WorkerTask:
        try:
            response = (
                self.client.messages.create(
                    model=task.model,
                    max_tokens=4096,
                    system=task.role,
                    messages=[{
                        "role": "user",
                        "content": task.description,
                    }],
                )
            )
            task.result = (
                response.content[0].text
            )
            task.status = "completed"
        except Exception as e:
            task.result = f"Error: {e}"
            task.status = "failed"
        return task

    def fan_out(
        self,
        tasks: list[WorkerTask],
        max_parallel: int = 5,
    ) -> list[WorkerTask]:
        with (
            concurrent.futures.ThreadPoolExecutor(
                max_workers=max_parallel
            ) as executor
        ):
            futures = {
                executor.submit(
                    self._execute_worker, task
                ): task
                for task in tasks
            }
            results = []
            for future in (
                concurrent.futures.as_completed(
                    futures
                )
            ):
                results.append(future.result())
        return results

    def gather(
        self,
        goal: str,
        results: list[WorkerTask],
        strategy: str = "synthesize",
    ) -> str:
        completed = [
            r for r in results
            if r.status == "completed"
        ]

        if strategy == "concatenate":
            return "\n\n---\n\n".join(
                f"## {r.id}: {r.role[:50]}"
                f"\n\n{r.result}"
                for r in completed
            )

        elif strategy == "synthesize":
            all_results = "\n\n".join(
                f"**{r.id}** ({r.role[:50]}):"
                f"\n{r.result}"
                for r in completed
            )
            response = (
                self.client.messages.create(
                    model=self.aggregator_model,
                    max_tokens=4096,
                    system=(
                        "Synthesize multiple expert"
                        " analyses into one report."
                        " Resolve contradictions."
                    ),
                    messages=[{
                        "role": "user",
                        "content": (
                            f"Goal: {goal}\n\n"
                            f"Analyses:\n"
                            f"{all_results}\n\n"
                            f"Synthesize."
                        ),
                    }],
                )
            )
            return response.content[0].text

        return "Unknown strategy"

    def execute(
        self,
        goal: str,
        perspectives: list[str],
        strategy: str = "synthesize",
    ) -> dict:
        tasks = self.decompose(
            goal, perspectives
        )
        results = self.fan_out(tasks)
        aggregated = self.gather(
            goal, results, strategy
        )
        completed = sum(
            1 for r in results
            if r.status == "completed"
        )
        failed = sum(
            1 for r in results
            if r.status == "failed"
        )
        return {
            "goal": goal,
            "workers": len(tasks),
            "completed": completed,
            "failed": failed,
            "report": aggregated,
        }


if __name__ == "__main__":
    # Live demo — needs ANTHROPIC_API_KEY.
    from anthropic import Anthropic as _Anthropic

    fog = FanOutGather(_Anthropic())
    out = fog.execute(
        goal="Review this authentication module for release readiness.",
        perspectives=["security", "performance", "style"],
    )
    print(f"workers={out['workers']} "
          f"completed={out['completed']} "
          f"failed={out['failed']}")
    print(out["report"])
