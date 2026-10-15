"""Validate aggregate withdrawal dimensions and delegate the pending-builder slice.

The single pending-builder-withdrawal provider uses its shared TARGET validator;
aggregate vectors retain their existing independent dimension recovery.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspects.base import _to_bool
from tests.generators.compliance_runners.state_transition.aspects.builder_withdrawals.builder_sweep_validator import (
    get_builder_sweep_solution,
)
from tests.generators.compliance_runners.state_transition.builder_pending_withdrawal_processing import (
    validate_case as pending_validate,
)
from tests.generators.compliance_runners.state_transition.provider import check_dimensions, decode

if TYPE_CHECKING:
    from pathlib import Path

_YAML = YAML(typ="safe")


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
    partial_sweep_withdrawal = any(
        withdrawal.validator_index < len(pre.validators)
        and spec.is_partially_withdrawable_validator(
            pre.validators[withdrawal.validator_index], pre.balances[withdrawal.validator_index]
        )
        for withdrawal in exp.withdrawals
    )

    dims: dict[str, str] = {
        "state_latest_block_hash_match": _to_bool(
            pre.latest_block_hash == pre.latest_execution_payload_bid.block_hash
        ).name,
        "builder_pending_withdrawals_exist": _to_bool(pre.builder_pending_withdrawals).name,
        "builder_pending_withdrawals_hit_limit": _to_bool(builder_hit).name,
        "validator_pending_withdrawals_exist": _to_bool(pre.pending_partial_withdrawals).name,
        "eligible_validator_pending_withdrawals_exist": _to_bool(
            any(w.withdrawable_epoch <= epoch for w in pre.pending_partial_withdrawals)
        ).name,
        "validator_pending_withdrawals_hit_limit": _to_bool(validator_hit).name,
        "validators_eligible_for_sweep_exist": _to_bool(validators_eligible).name,
        "partial_validator_sweep_withdrawal": _to_bool(partial_sweep_withdrawal).name,
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


def validate_case(case_dir: Path):
    metadata = _YAML.load((case_dir / "dimensions.yaml").read_text())
    claimed = metadata["claimed"]
    if "cmp_pending_amount_zero" in claimed:
        return pending_validate.for_spec(spec, case_dir)
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    actual = recover_withdrawal_processing(pre)
    return check_dimensions(claimed, actual)
