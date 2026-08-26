from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS, PtcWindowMaterializer

MODEL = Path(__file__).parent / "models" / "handler_ptc_window.mzn"
ASPECTS = {
    "epoch_context": ["epoch_position"],
    "state": ["validator_count", "validator_balance", "validator_activity"],
}


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ASPECTS, _nfaults)


def _nfaults(_r: dict) -> int:
    return 0


def build_profile(records, name):
    return _build_profile(records, name, ASPECTS, ASPECTS, {"outcome": ["outcome"]})


def materialize_profile(name: str, output_dir: Path | None = None) -> int:
    _, chosen = build_profile(_recs(), name)
    return PtcWindowMaterializer(spec).materialize_reps(
        output_dir or (Path(__file__).parent / "reftests"), [SimpleNamespace(**r) for r in chosen]
    )
