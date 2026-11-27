"""Recover quorum, queue occupancy, and withdrawal inputs from the pre-state."""

from tests.generators.compliance_runners.state_transition.aspects_helpers.queue_capacity import (
    queue_occupancy,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import NA


def observe_attributes(ctx):
    spec, pre = ctx.spec, ctx.pre
    spe = int(spec.SLOTS_PER_EPOCH)
    q = spec.get_builder_payment_quorum_threshold(pre)
    empty = spec.BuilderPendingPayment.empty()
    previous_payments = pre.builder_pending_payments[:spe]
    occupied = [p for p in previous_payments if p != empty]

    target_weight = int(occupied[0].weight) if occupied else NA

    previous_epoch_occupancy = queue_occupancy(len(occupied), spe)

    qualifying_payment_count = sum(p.weight >= q for p in previous_payments)

    quorum_relations = {
        "LT" if payment.weight < q else "GT" if payment.weight > q else "EQ" for payment in occupied
    }
    mixed_quorum_relations = {"LT", "EQ", "GT"}.issubset(quorum_relations)

    next_epoch_payments = pre.builder_pending_payments[spe:]
    next_epoch_nondefault_count = sum(p != empty for p in next_epoch_payments)
    next_epoch_payments_occupancy = queue_occupancy(
        next_epoch_nondefault_count, len(next_epoch_payments)
    )

    preexisting_withdrawals_count = len(pre.builder_pending_withdrawals)

    return {
        "observed_previous_epoch_occupancy": previous_epoch_occupancy,
        "observed_target_weight": target_weight,
        "observed_payment_quorum": int(q),
        "observed_qualifying_payment_count": qualifying_payment_count,
        "observed_mixed_quorum_relations": mixed_quorum_relations,
        "observed_next_epoch_payments_occupancy": next_epoch_payments_occupancy,
        "observed_preexisting_withdrawals_count": preexisting_withdrawals_count,
    }
