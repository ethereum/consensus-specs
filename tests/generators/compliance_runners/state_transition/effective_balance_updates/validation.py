"""Independent semantic validation for effective-balance-update vectors."""

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
    balance = pre.balances[_VALIDATOR_INDEX]
    effective_balance = validator.effective_balance
    increment = spec.EFFECTIVE_BALANCE_INCREMENT
    hysteresis_increment = increment // spec.HYSTERESIS_QUOTIENT
    downward_threshold = hysteresis_increment * spec.HYSTERESIS_DOWNWARD_MULTIPLIER
    upward_threshold = hysteresis_increment * spec.HYSTERESIS_UPWARD_MULTIPLIER
    update_downward = balance + downward_threshold < effective_balance
    update_upward = effective_balance + upward_threshold < balance
    max_effective_balance = spec.get_max_effective_balance(validator)
    rounded_balance = balance - balance % increment
    if not (update_downward or update_upward):
        hysteresis_result, outcome = "NO_CHANGE", "UNCHANGED"
    elif rounded_balance >= max_effective_balance:
        hysteresis_result, outcome = "CAPPED", "EFFECTIVE_BALANCE_CAPPED"
    elif update_downward:
        hysteresis_result, outcome = "DOWNWARD", "EFFECTIVE_BALANCE_UPDATED"
    else:
        hysteresis_result, outcome = "UPWARD", "EFFECTIVE_BALANCE_UPDATED"
    return {
        "credential_type": (
            "COMPOUNDING" if spec.has_compounding_withdrawal_credential(validator) else "STANDARD"
        ),
        "hysteresis_result": hysteresis_result,
        "balance_alignment": "EXACT_INCREMENT" if balance == rounded_balance else "ROUNDED_DOWN",
        "outcome": outcome,
    }


def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    return check_dimensions(claimed, recover_dimensions(pre))
