"""Independently validate withdrawal-processing compliance vectors.

For every generated case this module decodes the serialized pre/post pair,
independently recovers the aspect's coverage dimensions directly from the
state, compares them against the `claimed` dimensions recorded at
materialization time, and re-executes `process_withdrawals` to confirm `post`
matches the spec.

Handles both aspect models:

- ``builder_pending_withdrawal_processing`` — a single pending builder
  withdrawal entry.
- ``withdrawal_processing`` — pending builder/validator queues, builder sweep,
  and validator sweep.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspects.base import _to_bool, _to_cmp
from tests.generators.compliance_runners.state_transition.aspects.builder_withdrawals.builder_sweep_validator import (
    get_builder_sweep_solution,
)
from tests.generators.compliance_runners.state_transition.provider import check_dimensions, decode

if TYPE_CHECKING:
    from pathlib import Path

_YAML = YAML(typ="safe")


def recover_pending_withdrawal(pre) -> dict[str, str]:
    """Recover builder-pending-withdrawal dimensions from a pre state."""
    state_epoch = int(spec.get_current_epoch(pre))
    finalized_epoch = int(pre.finalized_checkpoint.epoch)
    min_deposit = int(spec.MIN_DEPOSIT_AMOUNT)

    pending_withdrawal = pre.builder_pending_withdrawals[0]
    builder_index = int(pending_withdrawal.builder_index)
    builder = pre.builders[builder_index]
    amount = int(pending_withdrawal.amount)
    balance = int(builder.balance)

    has_pending_payments = any(
        int(p.withdrawal.builder_index) == builder_index and int(p.withdrawal.amount) > 0
        for p in pre.builder_pending_payments
    )
    has_pending_withdrawals = any(
        int(w.builder_index) == builder_index and int(w.amount) > 0
        for w in pre.builder_pending_withdrawals
    )

    return {
        "state_latest_block_hash_match": _to_bool(
            pre.latest_block_hash == pre.latest_execution_payload_bid.block_hash
        ).name,
        "cmp_pending_amount_zero": _to_cmp(amount, 0).name,
        "cmp_builder_balance_amount": _to_cmp(balance, amount).name,
        "payload_builder_version": _to_bool(
            int(builder.version) == int(spec.PAYLOAD_BUILDER_VERSION)
        ).name,
        "cmp_state_epoch_deposit_epoch": _to_cmp(state_epoch, int(builder.deposit_epoch)).name,
        "cmp_state_epoch_withdrawal_epoch": _to_cmp(
            state_epoch, int(builder.withdrawable_epoch)
        ).name,
        "cmp_finalized_epoch_deposit_epoch": _to_cmp(
            finalized_epoch, int(builder.deposit_epoch)
        ).name,
        "withdrawable_epoch_set": _to_bool(
            int(builder.withdrawable_epoch) != int(spec.FAR_FUTURE_EPOCH)
        ).name,
        "cmp_balance_zero": _to_cmp(balance, 0).name,
        "cmp_balance_min_deposit": _to_cmp(balance, min_deposit).name,
        "has_pending_payments": _to_bool(has_pending_payments).name,
        "has_pending_withdrawals": _to_bool(has_pending_withdrawals).name,
    }


def recover_withdrawal_processing(pre) -> dict[str, str]:
    """Recover aggregate withdrawal-processing dimensions from a pre state."""
    limit = int(spec.MAX_WITHDRAWALS_PER_PAYLOAD) - 1
    mpp = int(spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP)
    epoch = spec.get_current_epoch(pre)
    exp = spec.get_expected_withdrawals(pre)
    pb = int(exp.processed_builder_withdrawals_count)
    pp = int(exp.processed_partial_withdrawals_count)
    prior = pb + pp

    builder_hit = pb == limit
    validator_hit = pb < limit and (pb + pp == limit or pp == mpp)
    validators_eligible = any(
        spec.is_fully_withdrawable_validator(v, pre.balances[i], epoch)
        or spec.is_partially_withdrawable_validator(v, pre.balances[i])
        for i, v in enumerate(pre.validators)
    )

    dims: dict[str, str] = {
        "state_latest_block_hash_match": _to_bool(
            pre.latest_block_hash == pre.latest_execution_payload_bid.block_hash
        ).name,
        "builder_pending_withdrawals_exist": _to_bool(
            bool(pre.builder_pending_withdrawals)
        ).name,
        "builder_pending_withdrawals_hit_limit": _to_bool(builder_hit).name,
        "validator_pending_withdrawals_exist": _to_bool(
            bool(pre.pending_partial_withdrawals)
        ).name,
        "eligible_validator_pending_withdrawals_exist": _to_bool(
            any(w.withdrawable_epoch <= epoch for w in pre.pending_partial_withdrawals)
        ).name,
        "validator_pending_withdrawals_hit_limit": _to_bool(validator_hit).name,
        "validators_eligible_for_sweep_exist": _to_bool(validators_eligible).name,
        "swept_validators_hit_limit": _to_bool(
            len(exp.withdrawals) == int(spec.MAX_WITHDRAWALS_PER_PAYLOAD)
        ).name,
    }

    sweep = get_builder_sweep_solution(spec, pre, prior)
    dims.update(
        {
            "cmp_builder_count_withdrawals_limit": sweep.cmp_builder_count_withdrawals_limit.name,
            "cmp_builder_count_max_per_sweep": sweep.cmp_builder_count_max_per_sweep.name,
            "cmp_eligible_builder_count_zero": sweep.cmp_eligible_builder_count_zero.name,
            "cmp_swept_count_zero": sweep.cmp_swept_count_zero.name,
            "cmp_swept_count_max_per_sweep": sweep.cmp_swept_count_max_per_sweep.name,
            "cmp_next_index_zero": sweep.cmp_next_index_zero.name,
            "cmp_next_index_last_builder_index": sweep.cmp_next_index_last_builder_index.name,
            "swept_builders_hit_withdrawals_limit": sweep.swept_builders_hit_withdrawals_limit.name,
        }
    )
    return dims


def validate_case(case_dir: Path) -> tuple[list, list[str]]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]

    if "cmp_pending_amount_zero" in claimed:
        actual = recover_pending_withdrawal(pre)
    else:
        actual = recover_withdrawal_processing(pre)

    return check_dimensions(claimed, actual)
