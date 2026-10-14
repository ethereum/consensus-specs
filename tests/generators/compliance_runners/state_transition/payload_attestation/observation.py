"""Recover payload-attestation inputs independently of generator metadata."""

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import NA
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled


def observe_attributes(ctx):
    spec, pre, operation = ctx.spec, ctx.pre, ctx.operation
    indexed = spec.get_indexed_payload_attestation(pre, operation)
    nonempty = len(indexed.attesting_indices) > 0
    bits = list(operation.aggregation_bits)
    shape = "EMPTY" if not any(bits) else "ALL" if all(bits) else "PARTIAL"
    signature = NA
    if nonempty:
        with bls_enabled():
            signature = bool(spec.is_valid_indexed_payload_attestation(pre, indexed))
    root = operation.data.beacon_block_root == pre.latest_block_header.parent_root
    slot = operation.data.slot + 1 == pre.slot
    if not root:
        outcome = "REJECT_PARENT_ROOT"
    elif not slot:
        outcome = "REJECT_SLOT"
    elif not nonempty:
        outcome = "REJECT_EMPTY"
    elif not signature:
        outcome = "REJECT_SIGNATURE"
    else:
        outcome = "ACCEPT"
    return {
        "parent_root_equal": root,
        "previous_slot": slot,
        "indices_shape": shape,
        "indices_nonempty": nonempty,
        "signature_ok": signature,
        "inferred_outcome": outcome,
        "post_present": ctx.post is not None,
    }
