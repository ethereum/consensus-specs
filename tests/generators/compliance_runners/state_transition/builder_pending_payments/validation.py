from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

from ..validation import check_dimensions, decode

Y = YAML(typ="safe")

def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    spe = int(spec.SLOTS_PER_EPOCH)
    q = spec.get_builder_payment_quorum_threshold(pre)
    claimed = Y.load((case_dir / "dimensions.yaml").read_text())["claimed"]

    appended = [p.withdrawal for p in pre.builder_pending_payments[:spe] if p.weight >= q]
    payments = list(pre.builder_pending_payments[spe:]) + [
        spec.BuilderPendingPayment() for _ in range(spe)
    ]
    withdrawals = list(pre.builder_pending_withdrawals) + appended

    expected = pre.copy()
    expected.builder_pending_payments = spec.BuilderPendingPayments(data=payments)
    expected.builder_pending_withdrawals = spec.BuilderPendingWithdrawals(data=withdrawals)

    first = list(pre.builder_pending_payments[:spe])
    occupied = [p for p in first if p != spec.BuilderPendingPayment()]

    relation = "NA"
    if occupied:
        if occupied[0].weight < q:
            relation = "LT"
        elif occupied[0].weight == q:
            relation = "EQ"
        else:
            relation = "GT"

    if not occupied:
        previous_epoch_occupancy = "EMPTY"
    elif len(occupied) == 1:
        previous_epoch_occupancy = "SINGLE"
    else:
        previous_epoch_occupancy = "MULTIPLE"

    if not occupied:
        target_amount_nonzero = "NA"
    elif occupied[0].withdrawal.amount:
        target_amount_nonzero = "T"
    else:
        target_amount_nonzero = "F"

    if not appended:
        qualifying_payment_count = "ZERO"
    elif len(appended) == 1:
        qualifying_payment_count = "ONE"
    else:
        qualifying_payment_count = "MULTIPLE_COUNT"

    quorum_relations = set()
    for payment in occupied:
        if payment.weight < q:
            quorum_relations.add("LT")
        elif payment.weight == q:
            quorum_relations.add("EQ")
        else:
            quorum_relations.add("GT")
    mixed_quorum_relations = {"LT", "EQ", "GT"}.issubset(quorum_relations)

    next_epoch_payments_nondefault = any(
        p != spec.BuilderPendingPayment() for p in pre.builder_pending_payments[spe:]
    )

    preexisting_withdrawals_nonempty = bool(pre.builder_pending_withdrawals)

    if not appended:
        withdrawals_appended = "ZERO"
    elif len(appended) == 1:
        withdrawals_appended = "ONE"
    else:
        withdrawals_appended = "MULTIPLE_COUNT"

    previous_epoch_discarded = all(p == spec.BuilderPendingPayment() for p in payments[spe:])

    next_epoch_shifted_forward = list(payments[:spe]) == list(pre.builder_pending_payments[spe:])

    new_tail_defaulted = all(p == spec.BuilderPendingPayment() for p in payments[spe:])

    if not occupied and not any(
        p != spec.BuilderPendingPayment() for p in pre.builder_pending_payments[spe:]
    ):
        outcome = "NO_STATE_CHANGE"
    elif not appended:
        outcome = "ROTATED_ONLY"
    elif len(appended) == 1:
        outcome = "APPENDED_ONE_AND_ROTATED"
    else:
        outcome = "APPENDED_MULTIPLE_AND_ROTATED"

    state_effected = expected.hash_tree_root() != pre.hash_tree_root()

    actual = {
        "previous_epoch_occupancy": previous_epoch_occupancy,
        "target_weight_to_quorum": relation,
        "target_amount_nonzero": target_amount_nonzero,
        "qualifying_payment_count": qualifying_payment_count,
        "mixed_quorum_relations": mixed_quorum_relations,
        "next_epoch_payments_nondefault": next_epoch_payments_nondefault,
        "preexisting_withdrawals_nonempty": preexisting_withdrawals_nonempty,
        "withdrawals_appended": withdrawals_appended,
        "previous_epoch_discarded": previous_epoch_discarded,
        "next_epoch_shifted_forward": next_epoch_shifted_forward,
        "new_tail_defaulted": new_tail_defaulted,
        "outcome": outcome,
        "state_effected": state_effected,
    }
    return check_dimensions(claimed, actual)
