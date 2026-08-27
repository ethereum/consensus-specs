"""Coverage profiles for Gloas ``process_payload_attestation``."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS, PayloadAttestationMaterializer

INPUT_ASPECTS = {
    "block_context": ["parent_root_matches", "slot_is_previous"],
    "participants": ["attesting_indices_profile", "attesting_indices_nonempty", "signature_valid"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
MODEL = Path(__file__).parent / "models" / "handler_payload_attestation.mzn"


def _nfaults(r: dict) -> int:
    return (
        int(not r["parent_root_matches"])
        + int(not r["slot_is_previous"])
        + int(not r["attesting_indices_nonempty"])
        + int(r["signature_valid"] == "F")
    )


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)


def build_profile(recs, name):
    return _build_profile(recs, name, ALL_ASPECTS, INPUT_ASPECTS, OUTCOME_ASPECT)


def materialize_profile(
    name: str,
    output_dir: Path | None = None,
) -> int:
    _, chosen = build_profile(_recs(), name)
    return PayloadAttestationMaterializer(spec, MODEL).materialize_reps(
        output_dir or (Path(__file__).parent / "reftests"), [SimpleNamespace(**r) for r in chosen]
    )
