"""Independent validation for ``process_slot`` sanity vectors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context
from tests.generators.compliance_runners.state_transition.provider import check_dimensions, decode

from .target import TARGET

if TYPE_CHECKING:
    from pathlib import Path

_YAML = YAML(typ="safe")


def validate_case(case_dir: Path):
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    post = decode(case_dir / "post.ssz_snappy", spec.BeaconState)
    slots = _YAML.load((case_dir / "slots.yaml").read_text())
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = TARGET.record(TARGET.observation(Context(spec, pre, slots, post, {})), "predicate")
    checks = check_dimensions(claimed, actual)

    expected_post = pre.copy()
    spec.process_slots(expected_post, spec.Slot(int(pre.slot) + int(slots)))
    errors = [] if expected_post == post else ["post-state differs from process_slots result"]
    return checks, errors
