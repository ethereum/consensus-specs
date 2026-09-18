from __future__ import annotations

from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspects.base import _to_bool, _to_cmp
from tests.generators.compliance_runners.state_transition.aspects_helpers.count import count_profile
from tests.generators.compliance_runners.state_transition.aspects_helpers.queue_capacity import (
    queue_occupancy,
)
from tests.generators.compliance_runners.state_transition.provider import check_dimensions, decode

if TYPE_CHECKING:
    from pathlib import Path

    from tests.generators.compliance_runners.state_transition.provider import Check

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
        relation = _to_cmp(occupied[0].weight, q).name

    previous_epoch_occupancy = queue_occupancy(len(occupied), len(first))

    if not occupied:
        target_amount_nonzero = "NA"
    else:
        target_amount_nonzero = _to_bool(bool(occupied[0].withdrawal.amount)).name

    qualifying_payment_count = count_profile(len(appended))

    quorum_relations = {_to_cmp(payment.weight, q).name for payment in occupied}
    mixed_quorum_relations = {"LT", "EQ", "GT"}.issubset(quorum_relations)

    next_epoch_payments = pre.builder_pending_payments[spe:]
    next_epoch_nondefault_count = sum(
        p != spec.BuilderPendingPayment() for p in next_epoch_payments
    )
    next_epoch_payments_occupancy = queue_occupancy(
        next_epoch_nondefault_count, len(next_epoch_payments)
    )

    preexisting_withdrawals_occupancy = count_profile(len(pre.builder_pending_withdrawals))

    if not occupied and next_epoch_payments_occupancy == "EMPTY":
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
        "next_epoch_payments_occupancy": next_epoch_payments_occupancy,
        "preexisting_withdrawals_occupancy": preexisting_withdrawals_occupancy,
        "outcome": outcome,
        "state_effected": state_effected,
    }
    return check_dimensions(claimed, actual)
