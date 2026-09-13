"""Offline demonstration of the four current reflection patterns.

The callbacks are deterministic stand-ins. No model, provider, real repository,
or production registry is contacted or changed.
"""
import json

if __package__:
    from . import reflection as r
else:
    import reflection as r


def arithmetic_check(task, artifact):
    expected = sum((19, 23))
    return "arithmetic:19+23", artifact == str(expected), f"expected {expected}"


class ArithmeticWorkspace:
    """Small in-memory adapter for showing rollback and verification order."""
    def __init__(self):
        self.total = 41

    def snapshot(self):
        return self.total

    def restore(self, checkpoint):
        self.total = checkpoint

    def versions(self):
        return {"inputs": "v1", "verifier": "v1"}

    def inspect_change(self, change):
        return r.ChangeScope(("calculation/total",), frozenset({"recalculate"}))

    def apply_atomic(self, change, policy):
        if not r.repair_allowed(r.RepairProposal(change), policy, self):
            raise PermissionError("repair outside policy")
        self.total = change

    def verify_protected(self):
        passed = self.total == sum((19, 23))
        return r.VerificationReport(passed, False, None if passed else "wrong total", ("arithmetic:19+23",))

    def artifact(self):
        return str(self.total)

    def result(self):
        return {"total": self.total}


def main():
    reviewed = r.generator_critic(
        "total the two line items", r.ReviewContract(("correct arithmetic",), 2),
        generate=lambda task: "41",
        revise=lambda task, artifact, critique: "42",
        critic=lambda task, artifact, contract, evidence: r.Critique(
            "accept" if all(e.passed for e in evidence) else "revise",
            evidence_ids=tuple(e.evidence_id for e in evidence),
        ),
        checks=(arithmetic_check,),
        select_best=lambda task, versions, checks: next(
            (v for v in reversed(versions) if arithmetic_check(task, v)[1]), versions[0]
        ),
    )
    recovered = r.self_heal(
        "wrong total", r.RecoveryPolicy(2, ("calculation",), ("checks",), frozenset({"recalculate"})),
        ArithmeticWorkspace(), lambda failure, history: failure,
        lambda diagnosis, policy: r.RepairProposal(42), lambda history: False,
    )
    candidate = r.SkillVersion(
        "checked-total", "1", "Total line items", "Compute and check the sum.",
        r.Applicability("arithmetic", {}, frozenset(), {}, 1),
    )
    def gate(name):
        return lambda skill: r.GateResult(True, "demo:" + name)
    admitted = r.admit_skill(candidate, gate("isolated"), gate("coexistence"), gate("trial"))

    lesson = r.Lesson(
        "check-total", "Recompute a reported total from its line items.",
        ["trace:arithmetic"], {"arithmetic"}, 1,
        "The proposed total disagreed with the independent sum.", ("arithmetic:19+23",),
    )
    r.admit_lesson(lesson, lambda candidate: candidate.independent_cases >= 3)
    recall_log = []
    recalled = r.recall_experience(
        r.RecallContext("next-task", "total another order", "arithmetic", {}, repeated_task=True),
        [lesson], lambda required, actual: True,
        lambda context, eligible, limit: eligible[:limit], 1,
        lambda **event: recall_log.append(event),
    )
    result = {
        "review": {"status": reviewed.status, "artifact": reviewed.artifact, "passes": len(reviewed.history)},
        "recovery": {"status": recovered["status"], "artifact": recovered["artifact"]},
        "skill": {"admitted": admitted, "state": candidate.state.value, "evidence": candidate.evidence_ids},
        "replay": {"lessons": [l.lesson_id for l in recalled], "phase": recall_log[0]["phase"]},
    }
    print(json.dumps(result, indent=2))
    assert reviewed.status == "accepted" and reviewed.artifact == "42"
    assert recovered["status"] == "recovered" and admitted
    assert recalled == [lesson]


if __name__ == "__main__":
    main()
