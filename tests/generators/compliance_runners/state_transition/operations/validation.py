"""Independent validation for ``process_operations`` vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context
from tests.generators.compliance_runners.state_transition.provider import check_dimensions, decode

from .target import TARGET

if TYPE_CHECKING:
    from pathlib import Path

_YAML = YAML(typ="safe")


def recover_dimensions(spec: Any, pre: Any, body: Any, post: Any) -> dict[str, Any]:
    values = TARGET.record(
        TARGET.observation(Context(spec, pre, body, post, {})),
        "predicate",
    )
    if not values["deposits_empty"]:
        outcome = "REJECT_DEPOSITS_NONZERO"
    else:
        outcomes = {
            "proposer_slashings_within_limit": "REJECT_PROPOSER_SLASHINGS_OVER_LIMIT",
            "attester_slashings_within_limit": "REJECT_ATTESTER_SLASHINGS_OVER_LIMIT",
            "attestations_within_limit": "REJECT_ATTESTATIONS_OVER_LIMIT",
            "voluntary_exits_within_limit": "REJECT_VOLUNTARY_EXITS_OVER_LIMIT",
            "bls_to_execution_changes_within_limit": "REJECT_BLS_TO_EXECUTION_CHANGES_OVER_LIMIT",
            "payload_attestations_within_limit": "REJECT_PAYLOAD_ATTESTATIONS_OVER_LIMIT",
        }
        outcome = next(
            (result for gate, result in outcomes.items() if not values[gate]),
            "ACCEPT_EMPTY",
        )
    values["outcome"] = outcome
    values["accepted"] = outcome == "ACCEPT_EMPTY"
    return values


def validate_case(case_dir: Path):
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    signed_block = decode(case_dir / "blocks_0.ssz_snappy", spec.SignedBeaconBlock)
    body = signed_block.message.body
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual_post = object() if (case_dir / "post.ssz_snappy").exists() else None
    actual = recover_dimensions(spec, pre, body, actual_post)
    return check_dimensions(claimed, actual)
