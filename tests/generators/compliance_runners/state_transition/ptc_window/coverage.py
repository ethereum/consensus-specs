from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    cover,
    enumerate_signatures,
)

from .materializer import _DIMS, PtcWindowMaterializer

MODEL = Path(__file__).parent / "models" / "handler_ptc_window.mzn"
ASPECTS = {
    "epoch_context": ["epoch_position"],
    "effects": [
        "old_sections_distinguishable",
        "tail_epoch_to_current",
        "retained_sections_shifted",
        "new_tail_recomputed",
        "state_effected",
    ],
    "outcome": ["outcome"],
}


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ASPECTS)


def build_profile(records, name):
    return cover(records, ASPECTS, 1 if name == "onewise" else 2)


def materialize_profile(name):
    _, chosen = build_profile(_recs(), name)
    return PtcWindowMaterializer(spec).materialize_reps(
        Path(__file__).parent / "reftests", [SimpleNamespace(**r) for r in chosen]
    )


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    records = _recs()
    if not args:
        for n in ("onewise", "pairwise", "standard"):
            obligations, cases = build_profile(records, n)
            print(f"{n}: {obligations} obligations, {len(cases)} cases")
        return 0
    materialize_profile(args[0]) if "--materialize" in sys.argv else None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
