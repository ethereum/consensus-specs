"""Observe preconditions independently of generation and of early rejection."""

from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.aspects_helpers.queue_churn import (
    queue_churn_variant,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import NA
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled


def observe_attributes(ctx):
    spec, pre, operation = ctx.spec, ctx.pre, ctx.operation
    signed_1, signed_2 = operation.signed_header_1, operation.signed_header_2
    h1, h2 = signed_1.message, signed_2.message
    current = int(spec.get_current_epoch(pre))
    found = int(h1.proposer_index) < len(pre.validators)
    proposer = pre.validators[h1.proposer_index] if found else None
    signatures = [NA, NA]
    if found:
        with bls_enabled():
            for i, signed in enumerate((signed_1, signed_2)):
                domain = spec.get_domain(
                    pre,
                    spec.DOMAIN_BEACON_PROPOSER,
                    spec.compute_epoch_at_slot(signed.message.slot),
                )
                # Both assertions use header_1's proposer, even when indices differ.
                signatures[i] = bool(
                    bls.Verify(
                        proposer.pubkey,
                        spec.compute_signing_root(signed.message, domain),
                        signed.signature,
                    )
                )
    epoch = spec.compute_epoch_at_slot(h1.slot)
    if epoch == spec.get_current_epoch(pre):
        window, index = (
            "CURRENT",
            int(spec.SLOTS_PER_EPOCH) + int(h1.slot) % int(spec.SLOTS_PER_EPOCH),
        )
    elif epoch == spec.get_previous_epoch(pre):
        window, index = "PREVIOUS", int(h1.slot) % int(spec.SLOTS_PER_EPOCH)
    else:
        window, index = "OLD", None
    return {
        "slot_1": int(h1.slot),
        "slot_2": int(h2.slot),
        "proposer_1": int(h1.proposer_index),
        "proposer_2": int(h2.proposer_index),
        "headers_equal": h1 == h2,
        "proposer_found": found,
        "slashed": bool(proposer.slashed) if found else NA,
        "activation_epoch": int(proposer.activation_epoch) if found else NA,
        "withdrawable_epoch": int(proposer.withdrawable_epoch) if found else NA,
        "exit_epoch": int(proposer.exit_epoch) if found else NA,
        "current_epoch": current,
        "valid_signature_1": signatures[0],
        "valid_signature_2": signatures[1],
        "window": window,
        "payment_matches": bool(
            pre.builder_pending_payments[index].proposer_index == h1.proposer_index
        )
        if index is not None
        else NA,
        "payment_present": bool(
            pre.builder_pending_payments[index] != spec.BuilderPendingPayment.empty()
        )
        if index is not None
        else False,
        "churn": queue_churn_variant(
            int(spec.compute_activation_exit_epoch(spec.Epoch(current))),
            int(pre.earliest_exit_epoch),
            int(proposer.effective_balance),
            int(pre.exit_balance_to_consume),
        )
        if found
        else NA,
        "post_present": ctx.post is not None,
        "payment_empty_after": bool(
            ctx.post.builder_pending_payments[index] == spec.BuilderPendingPayment.empty()
        )
        if ctx.post is not None and index is not None
        else NA,
    }
