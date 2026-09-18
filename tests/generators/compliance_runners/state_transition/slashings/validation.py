"""Independent semantic validation for slashings vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.provider import check_dimensions, decode

if TYPE_CHECKING:
    from pathlib import Path

    from tests.generators.compliance_runners.state_transition.provider import Check


_YAML = YAML(typ="safe")
_VALIDATOR_INDEX = 0


def recover_dimensions(pre: Any) -> dict[str, Any]:
    validator = pre.validators[_VALIDATOR_INDEX]
    epoch = spec.get_current_epoch(pre)
    total_active_balance = spec.get_total_active_balance(pre)
    increment = spec.EFFECTIVE_BALANCE_INCREMENT
    raw_slashings = sum(pre.slashings)
    adjusted_slashings = min(
        spec.Gwei(raw_slashings) * spec.PROPORTIONAL_SLASHING_MULTIPLIER_BELLATRIX,
        total_active_balance,
    )
    penalty_per_increment = adjusted_slashings // (total_active_balance // increment)
    due = validator.slashed and (
        epoch + spec.EPOCHS_PER_SLASHINGS_VECTOR // 2 == validator.withdrawable_epoch
    )
    penalty = (
        penalty_per_increment * (validator.effective_balance // increment) if due else spec.Gwei(0)
    )
    if not validator.slashed:
        validator_status = "UNSLASHED_VALIDATOR"
    elif not due:
        validator_status = "SLASHED_WAITING"
    else:
        validator_status = "SLASHED_DUE"
    if raw_slashings == 0:
        total_slashings = "ZERO_TOTAL"
    elif adjusted_slashings == total_active_balance:
        total_slashings = "SATURATED_TOTAL"
    else:
        total_slashings = "PARTIAL_TOTAL"
    if penalty == 0:
        penalty_outcome, outcome = "NO_PENALTY", "NO_STATE_CHANGE"
    elif penalty > pre.balances[_VALIDATOR_INDEX]:
        penalty_outcome, outcome = "UNDERFLOW_TO_ZERO", "BALANCE_ZEROED"
    elif penalty == pre.balances[_VALIDATOR_INDEX]:
        penalty_outcome, outcome = "FULL_PENALTY", "BALANCE_ZEROED"
    else:
        penalty_outcome, outcome = "PARTIAL_PENALTY", "BALANCE_DECREASED"
    return {
        "validator_status": validator_status,
        "total_slashings": total_slashings,
        "penalty_outcome": penalty_outcome,
        "outcome": outcome,
    }


def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    return check_dimensions(claimed, recover_dimensions(pre))
