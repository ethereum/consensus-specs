"""Validate DSL observations and the computed effective balance independently."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context
from tests.generators.compliance_runners.state_transition.provider import (
    Check,
    check_dimensions,
    decode,
)

from .target import TARGET

if TYPE_CHECKING:
    from pathlib import Path


_YAML = YAML(typ="safe")


def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    post = decode(case_dir / "post.ssz_snappy", spec.BeaconState)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    granularity = claimed.pop("granularity")
    target = TARGET.for_spec(spec)
    actual = target.record(target.observation(Context(spec, pre, None, post, {})), granularity)
    checks = check_dimensions(claimed, actual)

    validator = pre.validators[0]
    balance = int(pre.balances[0])
    old_effective = int(validator.effective_balance)
    increment = int(spec.EFFECTIVE_BALANCE_INCREMENT)
    hysteresis_increment = increment // int(spec.HYSTERESIS_QUOTIENT)
    downward = hysteresis_increment * int(spec.HYSTERESIS_DOWNWARD_MULTIPLIER)
    upward = hysteresis_increment * int(spec.HYSTERESIS_UPWARD_MULTIPLIER)
    expected = old_effective
    if balance + downward < old_effective or old_effective + upward < balance:
        expected = min(
            balance - balance % increment, int(spec.get_max_effective_balance(validator))
        )
    actual_effective = int(post.validators[0].effective_balance)
    checks.append(
        Check(
            "post_effective_balance",
            expected,
            actual_effective,
            "ok" if expected == actual_effective else "mismatch",
        )
    )
    return checks
