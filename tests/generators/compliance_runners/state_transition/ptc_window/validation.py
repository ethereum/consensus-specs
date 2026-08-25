from __future__ import annotations

from ..validation import Check, decode

from pathlib import Path

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

_YAML = YAML(typ="safe")

def validate_case(case_dir: Path) -> tuple[list[Check], list[str]]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = {
        "epoch_position": "GENESIS_END"
        if int(spec.get_current_epoch(pre)) == 0
        else "LATER_EPOCH_END",
        "validator_count": "MINIMUM" if len(pre.validators) == 64 else "MANY",
    }
    checks = [
        Check(k, v, actual.get(k), "ok" if actual.get(k) == v else "mismatch")
        for k, v in claimed.items()
    ]
    return checks, []
