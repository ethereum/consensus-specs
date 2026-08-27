from __future__ import annotations

from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.validation import (
    check_dimensions,
    decode,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests.generators.compliance_runners.state_transition.validation import Check

_YAML = YAML(typ="safe")

def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = {
        "epoch_position": "GENESIS_END"
        if int(spec.get_current_epoch(pre)) == 0
        else "LATER_EPOCH_END",
        "validator_count": "MINIMUM" if len(pre.validators) == 64 else "MANY",
        "validator_balance": (
            "MAXIMUM_BALANCE"
            if all(balance == spec.MAX_EFFECTIVE_BALANCE for balance in pre.balances)
            else (
                "MINIMUM_BALANCE"
                if all(balance == spec.EFFECTIVE_BALANCE_INCREMENT for balance in pre.balances)
                else "MIXED_BALANCE"
            )
        ),
        "validator_activity": (
            "ALL_ACTIVE"
            if all(
                validator.activation_epoch <= spec.get_current_epoch(pre)
                for validator in pre.validators
            )
            else "SOME_INACTIVE"
        ),
    }
    return check_dimensions(claimed, actual)
