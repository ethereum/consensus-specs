"""Independent semantic validation for ``process_block_header`` vectors."""

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


def validate_case(case_dir: Path) -> list:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    block = decode(case_dir / "block_header.ssz_snappy", spec.BeaconBlock)
    post = object() if (case_dir / "post.ssz_snappy").exists() else None
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = TARGET.record(TARGET.observation(Context(spec, pre, block, post, {})), "predicate")
    return check_dimensions(claimed, actual)
