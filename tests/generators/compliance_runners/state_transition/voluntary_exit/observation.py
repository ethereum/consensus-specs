"""Extract per-vector attributes independently of coverage declarations."""

from __future__ import annotations

from typing import Any

from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context, NA
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled


def observe_attributes(ctx: Context) -> dict[str, Any]:
    spec, pre, signed_exit = (ctx.spec, ctx.pre, ctx.operation)
    message = signed_exit.message
    validator_index = int(message.validator_index)
    validator_found = validator_index < len(pre.validators)
    current_epoch = int(spec.get_current_epoch(pre))
    message_epoch = int(message.epoch)
    activation_epoch = exit_epoch = effective_balance = signature_valid = NA
    if validator_found:
        validator = pre.validators[validator_index]
        activation_epoch = int(validator.activation_epoch)
        exit_epoch = int(validator.exit_epoch)
        effective_balance = int(validator.effective_balance)
        with bls_enabled():
            domain = spec.compute_domain(
                spec.DOMAIN_VOLUNTARY_EXIT,
                spec.config.CAPELLA_FORK_VERSION,
                pre.genesis_validators_root,
            )
            signing_root = spec.compute_signing_root(message, domain)
            signature_valid = bool(
                bls.Verify(validator.pubkey, signing_root, signed_exit.signature)
            )
    matching = [
        w for w in pre.pending_partial_withdrawals if int(w.validator_index) == validator_index
    ]
    return {
        "validator_index": validator_index,
        "validator_found": validator_found,
        "current_epoch": current_epoch,
        "message_epoch": message_epoch,
        "activation_epoch": activation_epoch,
        "exit_epoch": exit_epoch,
        "matching_pending": len(matching),
        "foreign_pending": len(pre.pending_partial_withdrawals) - len(matching),
        "pending_balance": sum(int(w.amount) for w in matching),
        "signature_valid": signature_valid,
        "earliest_exit_epoch": int(pre.earliest_exit_epoch),
        "new_exit_epoch": int(spec.compute_activation_exit_epoch(spec.Epoch(current_epoch))),
        "exit_balance_to_consume": int(pre.exit_balance_to_consume),
        "per_epoch_churn": int(spec.get_exit_churn_limit(pre)),
        "effective_balance": effective_balance,
    }
