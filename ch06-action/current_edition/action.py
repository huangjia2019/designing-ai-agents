"""Executable examples for revised Chapter 6, Listings 6.1-6.16.

Host applications supply trusted state, runners, verifiers and durable storage.
These examples do not initiate real transfers or supply an OS sandbox.
"""

# Listing 6.1 A minimal action contract and attempt record

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class ActionContract:
    effect: str
    target: str
    state_version: str
    commit_id: str
    request_digest: str
    acceptance_labels: tuple[str, ...]


@dataclass
class ActionAttempt:
    contract: ActionContract
    status: Literal[
        "proposed", "rejected", "started", "succeeded",
        "failed", "unknown", "accepted"
    ] = "proposed"
    evidence: dict[str, Any] = field(default_factory=dict)

# Listing 6.2 Artifact and gate records for a checked chain

from collections.abc import Callable


@dataclass(frozen=True)
class Artifact:
    kind: str
    schema_version: str
    payload: dict[str, Any]
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class GateResult:
    accepted: bool
    evidence: tuple[str, ...] = ()
    guidance: str = ""
    conclusive: bool = True

    def __post_init__(self) -> None:
        if type(self.accepted) is not bool:
            raise TypeError("accepted must be Boolean")
        if type(self.conclusive) is not bool:
            raise TypeError("conclusive must be Boolean")


Producer = Callable[[Artifact | None, str], Artifact]
Gate = Callable[[Artifact], GateResult]


@dataclass(frozen=True)
class ChainStep:
    step_id: str
    produce: Producer
    gate: Gate
    max_attempts: int = 2

# Listing 6.3 A chain runner that prevents rejected-artifact propagation

class GateRejected(RuntimeError):
    pass


def run_chain(
    steps: list[ChainStep],
    initial: Artifact | None = None,
) -> list[Artifact]:
    accepted: list[Artifact] = []
    upstream = initial

    for step in steps:
        guidance = ""
        for attempt in range(1, step.max_attempts + 1):
            candidate = step.produce(upstream, guidance)
            decision = step.gate(candidate)
            if decision.accepted:
                accepted.append(candidate)
                upstream = candidate
                break
            guidance = decision.guidance
        else:
            message = f"{step.step_id} failed its gate"
            raise GateRejected(message)

    return accepted

# Listing 6.4 A narrow gate for a verified patch artifact

def verified_patch_gate(
    artifact: Artifact,
    expected_revision: str,
) -> GateResult:
    data = artifact.payload
    checks = data.get("checks", {})
    evidence = tuple(data.get("evidence_refs", ()))

    if artifact.kind != "verified_patch":
        return GateResult(False, guidance="return a verified patch")
    if data.get("base_revision") != expected_revision:
        return GateResult(False, guidance="refresh the repository")
    if checks.get("focused") != "passed":
        return GateResult(False, evidence, "repair focused failures")
    if checks.get("integration") != "passed":
        return GateResult(False, evidence, "run integration checks")
    if not evidence:
        return GateResult(False, guidance="attach verifier evidence")
    return GateResult(True, evidence)

# Listing 6.5 Tool contracts and the current dispatch context

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from hashlib import sha256
from threading import Lock


ArgumentValidator = Callable[[Mapping[str, Any]], None]


@dataclass(frozen=True)
class TrustedValue:
    value: Any
    source_ref: str
    state_version: str
    read_at: datetime


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    effect: str
    roles: frozenset[str]
    stages: frozenset[str]
    validate_arguments: ArgumentValidator
    target_arg: str = "target"
    protected_args: frozenset[str] = frozenset()
    state_arg: str | None = None
    max_state_age_seconds: int | None = None
    mutates_state: bool = False
    acceptance_labels: tuple[str, ...] = (
        "preconditions",
        "postconditions",
    )

    def __post_init__(self) -> None:
        if self.state_arg not in (None, *self.protected_args):
            raise ValueError("state argument must be protected")
        if (
            self.max_state_age_seconds is not None
            and self.max_state_age_seconds <= 0
        ):
            raise ValueError("freshness limit must be positive")


@dataclass(frozen=True)
class DispatchContext:
    role: str
    stage: str
    granted_effects: frozenset[str]
    trusted_values: Mapping[str, TrustedValue]
    now: datetime
    commit_id: str | None = None


@dataclass(frozen=True)
class ToolIntent:
    tool_name: str
    arguments: Mapping[str, Any]

# Listing 6.6 Computing the eligible tool surface

class ToolRegistry:
    def __init__(self) -> None:
        self.specs: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self.specs:
            raise ValueError(f"duplicate tool: {spec.name}")
        self.specs[spec.name] = spec

    def eligible(self, context: DispatchContext) -> list[ToolSpec]:
        return [
            spec
            for spec in self.specs.values()
            if context.role in spec.roles
            and context.stage in spec.stages
            and spec.effect in context.granted_effects
        ]

    def summaries(self, context: DispatchContext) -> list[dict[str, str]]:
        return [
            {"name": item.name, "description": item.description}
            for item in self.eligible(context)
        ]

# Listing 6.7 Admission checks for one selected tool call

class AdmissionError(ValueError):
    pass


@dataclass(frozen=True)
class AdmittedCall:
    spec: ToolSpec
    contract: ActionContract
    arguments_json: str
    provenance: tuple[tuple[str, str], ...]
    state_read_at: datetime | None

    def arguments(self) -> dict[str, Any]:
        return json.loads(self.arguments_json)


class CommitStore:
    def __init__(self) -> None:
        self._digests: dict[str, str] = {}
        self._lock = Lock()

    def reserve(self, commit_id: str, digest: str) -> str:
        with self._lock:
            current = self._digests.get(commit_id)
            if current is None:
                self._digests[commit_id] = digest
                return "new"
            if current != digest:
                raise AdmissionError("commit identity changed arguments")
            return "repeat"

    def release(self, commit_id: str, digest: str) -> None:
        with self._lock:
            if self._digests.get(commit_id) == digest:
                del self._digests[commit_id]

    def digest_for(self, commit_id: str) -> str | None:
        with self._lock:
            return self._digests.get(commit_id)


def canonical_arguments(
    arguments: Mapping[str, Any],
) -> str:
    try:
        document = json.dumps(
            dict(arguments),
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise AdmissionError("arguments must be JSON values") from error
    return document


def request_digest(spec: ToolSpec, arguments_json: str) -> str:
    request = json.dumps(
        {
            "tool": spec.name,
            "effect": spec.effect,
            "arguments": json.loads(arguments_json),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(request.encode("utf-8")).hexdigest()


def admit(
    registry: ToolRegistry,
    intent: ToolIntent,
    context: DispatchContext,
) -> AdmittedCall:
    eligible = {item.name: item for item in registry.eligible(context)}
    spec = eligible.get(intent.tool_name)
    if spec is None:
        raise AdmissionError("tool is not eligible in this context")

    document = canonical_arguments(intent.arguments)
    digest = request_digest(spec, document)
    arguments = json.loads(document)
    try:
        spec.validate_arguments(arguments)
    except (TypeError, ValueError) as error:
        raise AdmissionError("tool arguments are invalid") from error

    provenance: list[tuple[str, str]] = []
    for name in spec.protected_args:
        trusted = context.trusted_values.get(name)
        if trusted is None or arguments.get(name) != trusted.value:
            raise AdmissionError(f"{name} is not runtime-bound")
        if not trusted.source_ref or not trusted.state_version:
            raise AdmissionError(
                f"trusted evidence is incomplete for {name}"
            )
        provenance.append((name, trusted.source_ref))

    state = (
        context.trusted_values.get(spec.state_arg)
        if spec.state_arg is not None
        else None
    )
    if spec.state_arg is not None and state is None:
        raise AdmissionError("trusted state basis is missing")
    if spec.max_state_age_seconds is not None:
        if state is None:
            raise AdmissionError("fresh state is required")
        if state.read_at.utcoffset() is None:
            raise AdmissionError("state timestamp needs a timezone")
        if context.now.utcoffset() is None:
            raise AdmissionError("runtime timestamp needs a timezone")
        age = (context.now - state.read_at).total_seconds()
        if age < 0 or age > spec.max_state_age_seconds:
            raise AdmissionError("state snapshot is stale")

    if spec.mutates_state and not context.commit_id:
        raise AdmissionError("commit identity is required")

    target = str(arguments.get(spec.target_arg, "unknown"))
    contract = ActionContract(
        effect=spec.effect,
        target=target,
        state_version=(state.state_version if state else "not-required"),
        commit_id=context.commit_id or "read-only",
        request_digest=digest,
        acceptance_labels=spec.acceptance_labels,
    )
    return AdmittedCall(
        spec=spec,
        contract=contract,
        arguments_json=document,
        provenance=tuple(provenance),
        state_read_at=(state.read_at if state else None),
    )

# Listing 6.8 Dispatching through the only executable entry point

def dispatch(
    registry: ToolRegistry,
    intent: ToolIntent,
    context: DispatchContext,
    commits: CommitStore,
    execute: Callable[[AdmittedCall], ActionAttempt],
) -> ActionAttempt:
    try:
        call = admit(registry, intent, context)
    except AdmissionError as error:
        spec = registry.specs.get(intent.tool_name)
        effect = spec.effect if spec else intent.tool_name
        target_arg = spec.target_arg if spec else "target"
        try:
            document = canonical_arguments(intent.arguments)
            digest = (
                request_digest(spec, document)
                if spec is not None
                else sha256(document.encode("utf-8")).hexdigest()
            )
        except AdmissionError:
            digest = "unresolved"
        contract = ActionContract(
            effect=effect,
            target=str(intent.arguments.get(target_arg, "unknown")),
            state_version="unresolved",
            commit_id=context.commit_id or "missing",
            request_digest=digest,
            acceptance_labels=("admission",),
        )
        attempt = ActionAttempt(contract)
        attempt.status = "rejected"
        attempt.evidence["reason"] = str(error)
        return attempt

    if call.spec.mutates_state:
        try:
            reservation = commits.reserve(
                call.contract.commit_id,
                call.contract.request_digest,
            )
        except AdmissionError as error:
            attempt = ActionAttempt(call.contract, status="rejected")
            attempt.evidence["reason"] = str(error)
            return attempt
        if reservation == "repeat":
            attempt = ActionAttempt(call.contract, status="unknown")
            attempt.evidence["reason"] = (
                "commit identity already exists; verify its effect"
            )
            attempt.evidence["admission"] = {
                "provenance": dict(call.provenance),
            }
            return attempt

    try:
        attempt = execute(call)
    except Exception as error:
        attempt = ActionAttempt(call.contract, status="unknown")
        attempt.evidence["executor_error"] = repr(error)

    runner_failure = attempt.evidence.get("runner_failure", {})
    safe_to_release = attempt.status == "rejected" or (
        attempt.status == "failed"
        and runner_failure.get("effect_started") is False
    )
    if call.spec.mutates_state and safe_to_release:
        commits.release(
            call.contract.commit_id,
            call.contract.request_digest,
        )
    attempt.evidence.setdefault("admission", {}).update(
        {
            "provenance": dict(call.provenance),
            "state_read_at": (
                call.state_read_at.isoformat()
                if call.state_read_at
                else None
            ),
        }
    )
    return attempt

# Listing 6.9 Versioned plan and step records

from enum import Enum


class StepStatus(str, Enum):
    TODO = "todo"
    RUNNING = "running"
    VERIFYING = "verifying"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class EvidenceRecord:
    kind: str
    reference: str
    accepted: bool

    def __post_init__(self) -> None:
        if type(self.accepted) is not bool:
            raise TypeError("accepted must be Boolean")


@dataclass
class PlanStep:
    step_id: str
    action: str
    target_ref: str
    dependencies: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    status: StepStatus = StepStatus.TODO
    attempt_ids: list[str] = field(default_factory=list)
    evidence: dict[str, EvidenceRecord] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    goal: str
    scope: frozenset[str]
    allowed_actions: frozenset[str]
    invariants: tuple[str, ...]
    version: int
    steps: dict[str, PlanStep]

# Listing 6.10 Selecting ready work and accepting a completed step

EvidenceVerifier = Callable[
    [PlanStep, Mapping[str, Any]],
    Mapping[str, EvidenceRecord],
]


def invalid_evidence(
    step: PlanStep,
    evidence: Mapping[str, EvidenceRecord],
) -> list[str]:
    return [
        name
        for name in step.required_evidence
        if name not in evidence
        or evidence[name].kind != name
        or evidence[name].accepted is not True
        or not evidence[name].reference
    ]


def validate_plan(plan: ExecutionPlan) -> None:
    if set(plan.steps) != {
        step.step_id for step in plan.steps.values()
    }:
        raise ValueError("plan keys and step identities differ")

    for step in plan.steps.values():
        if step.action not in plan.allowed_actions:
            raise ValueError(f"unauthorized action: {step.action}")
        if step.target_ref not in plan.scope:
            raise ValueError(f"target is outside scope: {step.target_ref}")
        unknown = set(step.dependencies) - set(plan.steps)
        if unknown:
            raise ValueError(f"unknown dependencies: {unknown}")
        unfinished = [
            name
            for name in step.dependencies
            if plan.steps[name].status is not StepStatus.DONE
        ]
        if step.status is StepStatus.DONE and unfinished:
            raise ValueError("accepted step has unfinished dependencies")
        if (
            step.status is StepStatus.DONE
            and invalid_evidence(step, step.evidence)
        ):
            raise ValueError("accepted step has invalid evidence")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str) -> None:
        if step_id in visiting:
            raise ValueError("plan contains a dependency cycle")
        if step_id in visited:
            return
        visiting.add(step_id)
        for dependency in plan.steps[step_id].dependencies:
            visit(dependency)
        visiting.remove(step_id)
        visited.add(step_id)

    for step_id in plan.steps:
        visit(step_id)


def ready_steps(plan: ExecutionPlan) -> list[PlanStep]:
    validate_plan(plan)
    done = {
        step.step_id
        for step in plan.steps.values()
        if step.status is StepStatus.DONE
    }
    return [
        step
        for step in plan.steps.values()
        if step.status is StepStatus.TODO
        and set(step.dependencies).issubset(done)
    ]


def accept_step(
    plan: ExecutionPlan,
    step_id: str,
    candidate: Mapping[str, Any],
    verify: EvidenceVerifier,
) -> None:
    validate_plan(plan)
    step = plan.steps[step_id]
    if step.status is not StepStatus.VERIFYING:
        raise ValueError("only verifying work can be accepted")
    unfinished = [
        name
        for name in step.dependencies
        if plan.steps[name].status is not StepStatus.DONE
    ]
    if unfinished:
        raise ValueError(f"unfinished dependencies: {unfinished}")
    evidence = verify(step, candidate)
    invalid = invalid_evidence(step, evidence)
    if invalid:
        raise ValueError(f"unaccepted evidence: {invalid}")
    step.evidence.update(evidence)
    step.status = StepStatus.DONE

# Listing 6.11 An atomic local checkpoint for the execution plan

import json
import os
from pathlib import Path


def checkpoint(plan: ExecutionPlan, destination: Path) -> None:
    validate_plan(plan)
    document = {
        "goal": plan.goal,
        "scope": sorted(plan.scope),
        "allowed_actions": sorted(plan.allowed_actions),
        "invariants": plan.invariants,
        "version": plan.version,
        "steps": {
            key: {
                "action": step.action,
                "target_ref": step.target_ref,
                "dependencies": step.dependencies,
                "required_evidence": step.required_evidence,
                "status": step.status.value,
                "attempt_ids": step.attempt_ids,
                "evidence": {
                    name: {
                        "kind": item.kind,
                        "reference": item.reference,
                        "accepted": item.accepted,
                    }
                    for name, item in step.evidence.items()
                },
            }
            for key, step in plan.steps.items()
        },
    }
    temporary = destination.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(document, stream, indent=2, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(destination)


def load_checkpoint(source: Path) -> ExecutionPlan:
    with source.open(encoding="utf-8") as stream:
        document = json.load(stream)
    steps = {
        key: PlanStep(
            step_id=key,
            action=item["action"],
            target_ref=item["target_ref"],
            dependencies=tuple(item["dependencies"]),
            required_evidence=tuple(item["required_evidence"]),
            status=StepStatus(item["status"]),
            attempt_ids=list(item["attempt_ids"]),
            evidence={
                name: EvidenceRecord(**record)
                for name, record in item["evidence"].items()
            },
        )
        for key, item in document["steps"].items()
    }
    plan = ExecutionPlan(
        goal=document["goal"],
        scope=frozenset(document["scope"]),
        allowed_actions=frozenset(document["allowed_actions"]),
        invariants=tuple(document["invariants"]),
        version=int(document["version"]),
        steps=steps,
    )
    validate_plan(plan)
    return plan

# Listing 6.12 Applying a bounded local replan

def apply_replan(
    plan: ExecutionPlan,
    affected: frozenset[str],
    replacements: Mapping[str, PlanStep],
) -> None:
    if not affected.issubset(plan.steps):
        raise ValueError("affected scope contains an unknown step")
    if not set(replacements).issubset(affected):
        raise ValueError("replan escaped the affected scope")
    if any(
        plan.steps[step_id].status
        not in {StepStatus.TODO, StepStatus.FAILED}
        for step_id in affected
    ):
        raise ValueError("affected scope contains protected work")

    prepared: dict[str, PlanStep] = {}
    for step_id, replacement in replacements.items():
        current = plan.steps[step_id]
        if current.status not in {StepStatus.TODO, StepStatus.FAILED}:
            raise ValueError(
                "replan can replace only pending or failed work"
            )
        if replacement.step_id != step_id:
            raise ValueError("replacement changed the step identity")
        if replacement.required_evidence != current.required_evidence:
            raise ValueError("replan changed the acceptance contract")
        current_external = set(current.dependencies) - affected
        new_external = set(replacement.dependencies) - affected
        if current_external != new_external:
            raise ValueError("replan changed a protected dependency")
        if replacement.status is not StepStatus.TODO:
            raise ValueError("replacement must begin as pending work")
        if replacement.attempt_ids or replacement.evidence:
            raise ValueError(
                "replacement cannot supply attempts or evidence"
            )
        prepared[step_id] = PlanStep(
            step_id=replacement.step_id,
            action=replacement.action,
            target_ref=replacement.target_ref,
            dependencies=replacement.dependencies,
            required_evidence=current.required_evidence,
            status=StepStatus.TODO,
            attempt_ids=list(current.attempt_ids),
            evidence=dict(current.evidence),
        )

    candidate = ExecutionPlan(
        goal=plan.goal,
        scope=plan.scope,
        allowed_actions=plan.allowed_actions,
        invariants=plan.invariants,
        version=plan.version + 1,
        steps={**plan.steps, **prepared},
    )
    validate_plan(candidate)
    plan.steps.update(prepared)
    plan.version = candidate.version

# Listing 6.13 Contracts for guarded execution

Guard = Callable[
    [ActionContract, Mapping[str, Any], Any | None],
    GateResult,
]
Runner = Callable[[ActionContract, Mapping[str, Any]], Any]


class RunnerFailure(RuntimeError):
    def __init__(
        self,
        reason: str,
        *,
        effect_started: bool,
        evidence: tuple[str, ...] = (),
    ) -> None:
        super().__init__(reason)
        self.effect_started = effect_started
        self.evidence = evidence


@dataclass(frozen=True)
class GuardedTool:
    name: str
    pre_checks: tuple[Guard, ...]
    runner: Runner
    post_checks: tuple[Guard, ...]

    def __post_init__(self) -> None:
        if not self.pre_checks or not self.post_checks:
            raise ValueError("guarded tools need pre and post checks")

# Listing 6.14 The guarded execution chokepoint

from copy import deepcopy


def run_guarded(
    tool: GuardedTool,
    contract: ActionContract,
    arguments: Mapping[str, Any],
) -> ActionAttempt:
    attempt = ActionAttempt(contract)
    requested = deepcopy(dict(arguments))
    runner_arguments = deepcopy(requested)
    attempt.evidence["requested_arguments"] = deepcopy(requested)
    attempt.evidence["runner_arguments"] = deepcopy(runner_arguments)
    attempt.evidence["request_digest"] = contract.request_digest

    for check in tool.pre_checks:
        try:
            result = check(
                contract,
                deepcopy(runner_arguments),
                None,
            )
            if not isinstance(result, GateResult):
                raise TypeError("pre-check returned an invalid result")
            attempt.evidence.setdefault("pre", []).append(
                result.evidence
            )
        except Exception as error:
            attempt.status = "rejected"
            attempt.evidence["pre_check_error"] = repr(error)
            return attempt
        if result.accepted is not True:
            attempt.status = "rejected"
            attempt.evidence["reason"] = result.guidance
            return attempt

    attempt.status = "started"
    try:
        output = tool.runner(
            contract,
            deepcopy(runner_arguments),
        )
        output_snapshot = deepcopy(output)
        attempt.status = "succeeded"
        attempt.evidence["runner_output"] = output_snapshot
    except RunnerFailure as error:
        attempt.status = "unknown" if error.effect_started else "failed"
        attempt.evidence["runner_failure"] = {
            "reason": str(error),
            "effect_started": error.effect_started,
            "evidence": error.evidence,
        }
        if error.effect_started:
            attempt.evidence["recovery_required"] = True
        return attempt
    except Exception as error:
        attempt.status = "unknown"
        attempt.evidence["runner_error"] = repr(error)
        attempt.evidence["recovery_required"] = True
        return attempt

    for check in tool.post_checks:
        try:
            result = check(
                contract,
                deepcopy(runner_arguments),
                deepcopy(output_snapshot),
            )
            if not isinstance(result, GateResult):
                raise TypeError("post-check returned an invalid result")
            attempt.evidence.setdefault("post", []).append(
                result.evidence
            )
        except Exception as error:
            attempt.status = "unknown"
            attempt.evidence["post_check_error"] = repr(error)
            attempt.evidence["recovery_required"] = True
            return attempt
        if result.accepted is not True:
            attempt.status = "failed" if result.conclusive else "unknown"
            attempt.evidence["reason"] = result.guidance
            if result.conclusive:
                attempt.evidence["compensation_required"] = True
            else:
                attempt.evidence["recovery_required"] = True
            return attempt

    attempt.status = "accepted"
    return attempt

# Listing 6.15 Payroll preconditions and postconditions

@dataclass(frozen=True)
class PaymentReceipt:
    receipt_id: str
    commit_id: str
    employee_id: str
    amount_cents: int
    state_version: str
    status: Literal["settled", "rejected"]


@dataclass
class PayrollEvidence:
    approved_amounts: Mapping[str, int]
    current_version: str
    commits: CommitStore
    payment_attempts: list[dict[str, Any]]
    provider_receipts: dict[str, PaymentReceipt]
    payroll_status: dict[str, str]


def make_payroll_pre(
    state: PayrollEvidence,
) -> Guard:
    def check(
        contract: ActionContract,
        arguments: Mapping[str, Any],
        output: Any | None,
    ) -> GateResult:
        approved_amount = state.approved_amounts.get(contract.target)
        if approved_amount is None:
            return GateResult(False, guidance="target is outside approval")
        if contract.state_version != state.current_version:
            return GateResult(False, guidance="refresh payroll state")
        if arguments.get("employee_id") != contract.target:
            return GateResult(False, guidance="employee identity changed")
        if arguments.get("amount_cents") != approved_amount:
            return GateResult(False, guidance="payment amount changed")
        reserved = state.commits.digest_for(contract.commit_id)
        if reserved != contract.request_digest:
            return GateResult(False, guidance="commit is not reserved")
        return GateResult(
            True,
            (
                "approved_target",
                "approved_amount",
                "fresh_version",
                "reserved_commit",
            ),
        )

    return check


def make_payroll_post(
    state: PayrollEvidence,
) -> Guard:
    def check(
        contract: ActionContract,
        arguments: Mapping[str, Any],
        output: Any | None,
    ) -> GateResult:
        amount = arguments.get("amount_cents")
        attempts = [
            item
            for item in state.payment_attempts
            if item.get("commit_id") == contract.commit_id
            and item.get("employee_id") == contract.target
            and item.get("amount_cents") == amount
            and item.get("state_version") == contract.state_version
        ]
        receipt = state.provider_receipts.get(contract.commit_id)
        receipt_ok = (
            receipt is not None
            and receipt.commit_id == contract.commit_id
            and receipt.employee_id == contract.target
            and receipt.amount_cents == amount
            and receipt.state_version == contract.state_version
            and receipt.status == "settled"
        )
        paid = state.payroll_status.get(contract.target) == "PAID"
        receipt_id = receipt.receipt_id if receipt else "missing"
        evidence = (
            f"attempts:{len(attempts)}",
            f"receipt:{receipt_id}",
        )
        if receipt is None or not attempts:
            return GateResult(
                False,
                evidence,
                "query the provider by commit identity",
                conclusive=False,
            )
        if len(attempts) != 1 or not receipt_ok or not paid:
            return GateResult(False, evidence, "reconcile payment effect")
        return GateResult(True, evidence)

    return check

# Listing 6.16 Argus routes every executable call through registered guards

class ArgusAction:
    def __init__(
        self,
        registry: ToolRegistry,
        guarded: Mapping[str, GuardedTool],
        commits: CommitStore,
    ) -> None:
        self.registry = registry
        self.guarded = dict(guarded)
        self.commits = commits
        self.trace: list[ActionAttempt] = []
        missing = set(registry.specs) - set(self.guarded)
        mismatched = {
            name
            for name, tool in self.guarded.items()
            if name != tool.name
        }
        if missing or mismatched:
            raise ValueError("registry and guarded bindings differ")

    def execute(
        self,
        intent: ToolIntent,
        context: DispatchContext,
    ) -> ActionAttempt:
        attempt = dispatch(
            self.registry,
            intent,
            context,
            self.commits,
            self._execute_guarded,
        )
        self.trace.append(deepcopy(attempt))
        return attempt

    def _execute_guarded(
        self,
        call: AdmittedCall,
    ) -> ActionAttempt:
        guarded = self.guarded.get(call.spec.name)
        if guarded is None or guarded.name != call.spec.name:
            attempt = ActionAttempt(call.contract, status="rejected")
            attempt.evidence["reason"] = "guarded path is missing"
            return attempt
        return run_guarded(
            guarded,
            call.contract,
            call.arguments(),
        )
