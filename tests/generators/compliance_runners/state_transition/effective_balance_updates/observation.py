"""Read one validator's inputs and output for the effective-balance target."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context


def observe_attributes(ctx: Context) -> dict:
    spec, pre, post = ctx.spec, ctx.pre, ctx.post
    validator = pre.validators[0]
    balance = int(pre.balances[0])
    effective = int(validator.effective_balance)
    increment = int(spec.EFFECTIVE_BALANCE_INCREMENT)
    return {
        "balance": balance,
        "effective_balance": effective,
        "rounded_balance": balance - balance % increment,
        "max_effective_balance": int(spec.get_max_effective_balance(validator)),
        "is_compounding": bool(spec.has_compounding_withdrawal_credential(validator)),
        "post_effective_balance": int(post.validators[0].effective_balance),
    }
