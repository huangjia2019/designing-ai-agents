# Current Chapter 7 examples. All runtime services are explicit adapters.
# Requires Python 3.10+; standard library only.

# Listing 7.1 Review contract and critique records
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    source: str
    passed: bool | None
    detail: str


@dataclass(frozen=True)
class Critique:
    verdict: Literal["accept", "revise", "stop"]
    issues: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewContract:
    criteria: tuple[str, ...]
    max_reviews: int

# Listing 7.2 Gathering evidence through independent checks
def gather_review_evidence(
    task: str,
    artifact: str,
    checks,
) -> tuple[EvidenceItem, ...]:
    items = []
    for check in checks:
        evidence_id, passed, detail = check(task, artifact)
        items.append(EvidenceItem(
            evidence_id=evidence_id,
            source=check.__name__,
            passed=passed,
            detail=detail,
        ))
    return tuple(items)

# Listing 7.3 Reviewing one artifact version
@dataclass(frozen=True)
class ReviewStep:
    artifact: str
    evidence: tuple[EvidenceItem, ...]
    critique: Critique


def review_once(task, artifact, contract, critic, checks):
    evidence = gather_review_evidence(task, artifact, checks)
    report = critic(task, artifact, contract, evidence)
    return ReviewStep(artifact, evidence, report)

# Listing 7.4 A bounded Generator-Critic chain
@dataclass
class ReviewResult:
    artifact: str
    status: str
    history: list[ReviewStep] = field(default_factory=list)


def generator_critic(
    task,
    contract,
    generate,
    revise,
    critic,
    checks,
    select_best,
):
    artifact = generate(task)
    versions = [artifact]
    history = []

    for _ in range(contract.max_reviews):
        step = review_once(
            task,
            artifact,
            contract,
            critic,
            checks,
        )
        history.append(step)
        if step.critique.verdict == "accept":
            return ReviewResult(artifact, "accepted", history)
        if step.critique.verdict == "stop":
            best = select_best(task, versions, checks)
            return ReviewResult(best, "unresolved", history)

        artifact = revise(task, artifact, step.critique)
        versions.append(artifact)

    best = select_best(task, versions, checks)
    return ReviewResult(best, "budget_exhausted", history)

# Listing 7.5 Recovery policy and state records
@dataclass(frozen=True)
class RecoveryPolicy:
    max_attempts: int
    writable_paths: tuple[str, ...]
    protected_paths: tuple[str, ...]
    allowed_tools: frozenset[str]


@dataclass(frozen=True)
class RepairProposal:
    change: object


@dataclass(frozen=True)
class ChangeScope:
    paths: tuple[str, ...]
    tools: frozenset[str]


@dataclass(frozen=True)
class VerificationReport:
    passed: bool
    regressed: bool
    failure: str | None
    evidence_ids: tuple[str, ...]


@dataclass
class RecoveryState:
    original_failure: str
    failure: str
    baseline: object
    versions: dict[str, str]
    history: list[dict] = field(default_factory=list)

# Listing 7.6 Capturing a restorable recovery baseline
def capture_recovery(workspace, failure: str) -> RecoveryState:
    return RecoveryState(
        original_failure=failure,
        failure=failure,
        baseline=workspace.snapshot(),
        versions=workspace.versions(),
    )

# Listing 7.7 Checking a repair against its authority envelope
from pathlib import PurePosixPath
from posixpath import normpath


def under(path: str, root: str) -> bool:
    value = PurePosixPath(normpath(path))
    boundary = PurePosixPath(normpath(root))
    return value == boundary or boundary in value.parents


def repair_allowed(
    proposal: RepairProposal,
    policy: RecoveryPolicy,
    workspace,
) -> bool:
    scope: ChangeScope = workspace.inspect_change(proposal.change)
    if not scope.paths and not scope.tools:
        return False
    if not scope.tools <= policy.allowed_tools:
        return False
    if any(
        under(path, root)
        for path in scope.paths
        for root in policy.protected_paths
    ):
        return False
    return all(
        any(under(path, root) for root in policy.writable_paths)
        for path in scope.paths
    )

# Listing 7.8 Applying and verifying one repair attempt
def apply_and_verify(workspace, proposal, policy):
    checkpoint = workspace.snapshot()
    try:
        workspace.apply_atomic(proposal.change, policy)
        report = workspace.verify_protected()
    except Exception:
        workspace.restore(checkpoint)
        raise
    if not report.passed or report.regressed:
        workspace.restore(checkpoint)
    return report, checkpoint

# Listing 7.9 A policy-bounded Self-Heal Loop
def handoff(workspace, state, reason):
    workspace.restore(state.baseline)
    return {
        "status": "handed_off",
        "reason": reason,
        "original_failure": state.original_failure,
        "versions": state.versions,
        "baseline_restored": True,
        "history": state.history,
    }


def self_heal(failure, policy, workspace, diagnose, propose, no_progress):
    state = capture_recovery(workspace, failure)

    for attempt_no in range(policy.max_attempts):
        diagnosis = diagnose(state.failure, state.history)
        proposal = propose(diagnosis, policy)
        if not repair_allowed(proposal, policy, workspace):
            return handoff(workspace, state, "outside_authority")

        try:
            report, checkpoint = apply_and_verify(
                workspace,
                proposal,
                policy,
            )
        except Exception as error:
            state.history.append({
                "attempt": attempt_no + 1,
                "diagnosis": diagnosis,
                "proposal": proposal,
                "error": type(error).__name__,
            })
            return handoff(workspace, state, "apply_error")
        state.history.append({
            "attempt": attempt_no + 1,
            "diagnosis": diagnosis,
            "proposal": proposal,
            "checkpoint": checkpoint,
            "report": report,
        })
        if report.passed and not report.regressed:
            return {
                "status": "recovered",
                "artifact": workspace.artifact(),
                "result": workspace.result(),
                "history": state.history,
            }
        if report.regressed:
            return handoff(workspace, state, "regression")
        if no_progress(state.history):
            return handoff(workspace, state, "no_progress")
        state.failure = report.failure or state.failure

    return handoff(workspace, state, "budget_exhausted")

# Listing 7.10 Skill candidate and applicability records
from enum import Enum
from typing import Protocol


class SkillState(str, Enum):
    CANDIDATE = "candidate"
    TRIAL = "trial"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


@dataclass(frozen=True)
class Applicability:
    task_family: str
    conditions: dict[str, str]
    required_permissions: frozenset[str]
    dependency_spec: dict[str, str]
    max_risk: int


@dataclass
class SkillVersion:
    skill_id: str
    version: str
    description: str
    instructions: str
    applies: Applicability
    state: SkillState = SkillState.CANDIDATE
    evidence_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GateResult:
    passed: bool
    evidence_id: str
    failures: tuple[str, ...] = ()


class Gate(Protocol):
    def __call__(self, skill: SkillVersion) -> GateResult:
        ...

# Listing 7.11 Evidence-backed Skill admission
def admit_skill(
    skill: SkillVersion,
    isolated: Gate,
    coexistence: Gate,
    canary: Gate,
) -> bool:
    if skill.state != SkillState.CANDIDATE:
        raise ValueError("admission requires a candidate")

    for gate in (isolated, coexistence):
        result = gate(skill)
        if result.evidence_id:
            skill.evidence_ids.append(result.evidence_id)
        if not result.passed or not result.evidence_id:
            return False

    skill.state = SkillState.TRIAL
    result = canary(skill)
    if result.evidence_id:
        skill.evidence_ids.append(result.evidence_id)
    if not result.passed or not result.evidence_id:
        skill.state = SkillState.CANDIDATE
        return False

    skill.state = SkillState.ACTIVE
    return True

# Listing 7.12 Hard filters for active Skills
@dataclass(frozen=True)
class TaskRequest:
    text: str
    family: str
    attributes: dict[str, str]
    risk: int
    permissions: frozenset[str]
    dependencies: dict[str, str]


def hard_allowed(task, skill, compatible, matches) -> bool:
    applies = skill.applies
    return (
        skill.state == SkillState.ACTIVE
        and task.family == applies.task_family
        and matches(task.attributes, applies.conditions)
        and task.risk <= applies.max_risk
        and applies.required_permissions <= task.permissions
        and compatible(
            task.dependencies,
            applies.dependency_spec,
        )
    )

# Listing 7.13 Layered Skill routing with abstention
def route_skill(
    task,
    skills,
    compatible,
    matches,
    narrow,
    choose,
    record,
):
    legal = [
        skill
        for skill in skills
        if hard_allowed(task, skill, compatible, matches)
    ]
    legal_by_key = {
        (skill.skill_id, skill.version): skill
        for skill in legal
    }
    ranked_keys = [
        (skill.skill_id, skill.version)
        for skill in narrow(task, legal)
    ]
    shortlist = [
        legal_by_key[key]
        for key in dict.fromkeys(ranked_keys)
        if key in legal_by_key
    ]
    if not shortlist:
        record(task, legal, shortlist, None, "general solver")
        return None

    if len(shortlist) == 1:
        selected = shortlist[0]
        record(task, legal, shortlist, selected, "one qualified Skill")
        return selected

    decision = choose(task, shortlist)
    if decision is None:
        record(task, legal, shortlist, None, "selector abstained")
        return None
    selected_key, reason = decision
    selected = next(
        (
            s
            for s in shortlist
            if (s.skill_id, s.version) == selected_key
        ),
        None,
    )
    if selected is None:
        record(task, legal, shortlist, None, "selector abstained")
        return None

    record(task, legal, shortlist, selected, reason)
    return selected

# Listing 7.14 Operating evidence and reversible withdrawal
@dataclass(frozen=True)
class SkillRunEvidence:
    task_family: str
    legal_versions: tuple[str, ...]
    selected_version: str | None
    agent_version: str
    harness_version: str
    dependencies: dict[str, str]
    outcome: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class WithdrawalEvidence:
    reason: str
    evidence_ids: tuple[str, ...]
    reversible: bool
    rollback_version: str
    approval_id: str | None = None


def withdraw_skill(
    registry,
    skill,
    evidence,
) -> bool:
    if not evidence.reason or not evidence.evidence_ids:
        return False
    if not registry.valid_evidence(evidence.evidence_ids, skill):
        return False
    if not evidence.reversible:
        return False
    if not registry.has_version(
        skill.skill_id,
        evidence.rollback_version,
    ):
        return False
    protected_scope = registry.is_protected(skill)
    if protected_scope and not registry.valid_approval(
        evidence.approval_id,
        skill,
    ):
        return False
    with registry.atomic_change():
        registry.archive(skill, evidence.rollback_version)
        registry.remove_from_routes(skill.skill_id, skill.version)
        registry.record_withdrawal(skill, evidence)
        skill.state = SkillState.DEPRECATED
    return True

# Listing 7.15 Experience records and replay status
class ReplayStatus(str, Enum):
    CANDIDATE = "candidate"
    REPLAYABLE = "replayable"
    CONFLICTED = "conflicted"
    RETIRED = "retired"


@dataclass(frozen=True)
class ExecutionTrace:
    task_id: str
    task: str
    task_family: str
    steps: tuple[dict, ...]
    outcome: str | None
    evidence_ids: tuple[str, ...]
    versions: dict[str, str]


@dataclass
class Lesson:
    lesson_id: str
    text: str
    source_trace_ids: list[str]
    task_families: set[str]
    independent_cases: int
    causal_mechanism: str | None
    external_evidence_ids: tuple[str, ...]
    status: ReplayStatus = ReplayStatus.CANDIDATE
    version_constraints: dict[str, str] = field(
        default_factory=dict
    )
    unresolved_conflicts: set[str] = field(
        default_factory=set
    )

# Listing 7.16 Admitting a scoped lesson for replay
def can_admit_lesson(lesson, repeated_case_gate) -> bool:
    repeated = repeated_case_gate(lesson)
    causal = (
        bool(lesson.causal_mechanism)
        and bool(lesson.external_evidence_ids)
    )
    return (
        lesson.status == ReplayStatus.CANDIDATE
        and bool(lesson.source_trace_ids)
        and bool(lesson.task_families)
        and not lesson.unresolved_conflicts
        and (repeated or causal)
    )


def admit_lesson(lesson, repeated_case_gate) -> bool:
    if not can_admit_lesson(lesson, repeated_case_gate):
        return False
    lesson.status = ReplayStatus.REPLAYABLE
    return True

# Listing 7.17 Choosing the Experience Replay phase
@dataclass(frozen=True)
class RecallContext:
    task_id: str
    task: str
    task_family: str
    versions: dict[str, str]
    high_risk: bool = False
    repeated_task: bool = False
    failed: bool = False
    low_confidence: bool = False
    environment_changed: bool = False
    replanning: bool = False


def recall_phase(ctx: RecallContext) -> str | None:
    recovery = (
        ctx.failed
        or ctx.low_confidence
        or ctx.environment_changed
        or ctx.replanning
    )
    if recovery:
        return "recovery"
    if ctx.high_risk or ctx.repeated_task:
        return "preflight"
    return None

# Listing 7.18 Task-sensitive and trigger-sensitive recall
def recall_experience(
    ctx,
    lessons,
    version_check,
    narrow,
    limit,
    record,
):
    if limit <= 0:
        return []
    phase = recall_phase(ctx)
    if phase is None:
        return []

    eligible = [
        lesson
        for lesson in lessons
        if lesson.status == ReplayStatus.REPLAYABLE
        and ctx.task_family in lesson.task_families
        and not lesson.unresolved_conflicts
        and version_check(
            lesson.version_constraints,
            ctx.versions,
        )
    ]
    eligible_by_id = {x.lesson_id: x for x in eligible}
    selected = []
    seen = set()
    for item in narrow(ctx, eligible, limit):
        if item.lesson_id not in eligible_by_id:
            continue
        if item.lesson_id in seen:
            continue
        selected.append(eligible_by_id[item.lesson_id])
        seen.add(item.lesson_id)
        if len(selected) == limit:
            break
    record(
        task_id=ctx.task_id,
        phase=phase,
        eligible_ids=[x.lesson_id for x in eligible],
        selected_ids=[x.lesson_id for x in selected],
    )
    return selected

# Listing 7.19 Coordinating review, verification, and recovery
@dataclass(frozen=True)
class TaskTrace:
    task_id: str
    artifact: str
    review_status: str
    recovery_status: str
    delivery_status: str
    evidence_ids: tuple[str, ...]

class ReflectionCoordinator:
    def __init__(self, review, verify, heal, record):
        self.review = review
        self.verify = verify
        self.heal = heal
        self.record = record

    def complete(self, task) -> TaskTrace:
        reviewed = self.review(task)
        review_ids = tuple(
            item.evidence_id
            for step in reviewed.history
            for item in step.evidence
        )
        if reviewed.status != "accepted":
            trace = TaskTrace(
                task_id=task.task_id,
                artifact=reviewed.artifact,
                review_status=reviewed.status,
                recovery_status="not_started",
                delivery_status="handed_off",
                evidence_ids=review_ids,
            )
            self.record(trace)
            return trace

        report = self.verify(reviewed.artifact)
        verified = report.passed and not report.regressed
        artifact = reviewed.artifact
        recovery_status = "not_needed"
        recovery_ids = ()
        if not verified:
            healed = self.heal(
                report.failure or "protected_verifier_failed"
            )
            recovery_status = healed["status"]
            if recovery_status == "recovered":
                if "artifact" not in healed:
                    recovery_status = "invalid_recovery_record"
                else:
                    artifact = healed["artifact"]
            recovery_ids = tuple(
                evidence_id
                for attempt in healed["history"]
                for evidence_id in getattr(
                    attempt.get("report"),
                    "evidence_ids",
                    (),
                )
            )

        same_version = artifact == reviewed.artifact
        deliverable = verified or (
            recovery_status == "recovered" and same_version
        )
        delivery_status = "accepted" if deliverable else "handed_off"
        trace = TaskTrace(
            task_id=task.task_id,
            artifact=artifact,
            review_status=reviewed.status,
            recovery_status=recovery_status,
            delivery_status=delivery_status,
            evidence_ids=(
                review_ids + report.evidence_ids + recovery_ids
            ),
        )
        self.record(trace)
        return trace

# Listing 7.20 Deciding release from protected evidence
@dataclass(frozen=True)
class SignalResult:
    name: str
    passed: bool
    hard_gate: bool
    evidence_id: str
    cost: float


@dataclass(frozen=True)
class ReleaseDecision:
    allowed: bool
    blocking_signals: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    total_cost: float


def decide_release(results) -> ReleaseDecision:
    if not results:
        return ReleaseDecision(
            allowed=False,
            blocking_signals=("missing_evidence",),
            evidence_ids=(),
            total_cost=0.0,
        )

    blockers = tuple(
        result.name
        for result in results
        if result.hard_gate and not result.passed
    )
    return ReleaseDecision(
        allowed=not blockers,
        blocking_signals=blockers,
        evidence_ids=tuple(
            result.evidence_id for result in results
        ),
        total_cost=sum(result.cost for result in results),
    )
