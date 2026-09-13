"""Run a salary-transfer simulation without a model or payment provider."""

from datetime import datetime, timezone
import json

from .action import (
    ArgusAction, CommitStore, DispatchContext, GuardedTool, PaymentReceipt,
    PayrollEvidence, ToolIntent, ToolRegistry, ToolSpec, TrustedValue,
    make_payroll_post, make_payroll_pre,
)


def run_demo() -> dict:
    now = datetime(2026, 9, 13, 9, tzinfo=timezone.utc)
    employee_id, amount_cents = "E0007", 12_500
    version = "payroll:v17"
    commits = CommitStore()
    state = PayrollEvidence(
        approved_amounts={employee_id: amount_cents},
        current_version=version,
        commits=commits,
        payment_attempts=[],
        provider_receipts={},
        payroll_status={},
    )

    def validate(arguments):
        amount = arguments.get("amount_cents")
        if type(amount) is not int or amount <= 0:
            raise ValueError("amount must be positive integer cents")

    registry = ToolRegistry()
    registry.register(ToolSpec(
        name="transfer_salary",
        description="Transfer one approved salary",
        effect="payroll.transfer",
        roles=frozenset({"payroll_operator"}),
        stages=frozenset({"payment"}),
        validate_arguments=validate,
        target_arg="employee_id",
        protected_args=frozenset({"employee_id", "amount_cents"}),
        state_arg="employee_id",
        max_state_age_seconds=60,
        mutates_state=True,
    ))
    trusted = {
        key: TrustedValue(
            value=value, source_ref=f"payroll://{employee_id}/{key}",
            state_version=version, read_at=now,
        )
        for key, value in (
            ("employee_id", employee_id), ("amount_cents", amount_cents),
        )
    }
    context = DispatchContext(
        role="payroll_operator", stage="payment",
        granted_effects=frozenset({"payroll.transfer"}),
        trusted_values=trusted, now=now,
        commit_id="pay:2026-09:E0007",
    )

    def simulated_provider(contract, arguments):
        # The host runner receives the reserved identity, not a model override.
        state.payment_attempts.append({
            "commit_id": contract.commit_id,
            "employee_id": arguments["employee_id"],
            "amount_cents": arguments["amount_cents"],
            "state_version": version,
        })
        state.provider_receipts[contract.commit_id] = PaymentReceipt(
            receipt_id="simulation-receipt-1",
            commit_id=contract.commit_id,
            employee_id=arguments["employee_id"],
            amount_cents=arguments["amount_cents"],
            state_version=version, status="settled",
        )
        state.payroll_status[arguments["employee_id"]] = "PAID"
        return {"provider_receipt": "simulation-receipt-1"}

    guarded = GuardedTool(
        name="transfer_salary",
        pre_checks=(make_payroll_pre(state),),
        runner=simulated_provider,
        post_checks=(make_payroll_post(state),),
    )
    agent = ArgusAction(registry, {"transfer_salary": guarded}, commits)
    intent = ToolIntent(
        "transfer_salary",
        {"employee_id": employee_id, "amount_cents": amount_cents},
    )
    first = agent.execute(intent, context)
    repeated = agent.execute(intent, context)
    changed = agent.execute(
        ToolIntent("transfer_salary", {
            "employee_id": employee_id, "amount_cents": 99_999_999,
        }), context,
    )
    return {
        "mode": "offline simulation; no money moves",
        "first_attempt": first.status,
        "same_commit_repeated": repeated.status,
        "changed_amount": changed.status,
        "provider_calls": len(state.payment_attempts),
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
