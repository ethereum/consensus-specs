"""Validate payload-attestation vectors using shared observations."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context, NA
from tests.generators.compliance_runners.state_transition.provider import check_dimensions, decode

from .target import TARGET

if TYPE_CHECKING:
    from pathlib import Path

    from tests.generators.compliance_runners.state_transition.provider import Check

_YAML = YAML(typ="safe")


def recover(pre: Any, operation: Any, post: Any | None = None) -> dict[str, Any]:
    target = TARGET.for_spec(spec)
    record = target.record(target.observation(Context(spec, pre, operation, post, {})))
    return {name: "NA" if value is NA else value for name, value in record.items()}


def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    operation = decode(case_dir / "payload_attestation.ssz_snappy", spec.PayloadAttestation)
    post_path = case_dir / "post.ssz_snappy"
    post = decode(post_path, spec.BeaconState) if post_path.exists() else None
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, operation, post)
    return check_dimensions(claimed, actual)
