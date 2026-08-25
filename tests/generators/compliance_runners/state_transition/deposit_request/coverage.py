"""Coverage profiles for process_deposit_request.

This handler has no rejections, so there is no normal/exceptional split — just a
combinatorial sweep over its one control-flow dimension (`start_index_unset`) and
two input-shape dimensions. `standard` = pairwise over all aspects.

Run:
    uv run python -m ...deposit_request.coverage
    uv run python -m ...deposit_request.coverage standard --materialize
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from ..aspect_coverage import cover, enumerate_signatures
from .materializer import DepositRequestMaterializer, _DIMS

INPUT_ASPECTS = {
    "deposit_amount": ["amount_nonzero"],
    "deposit_pubkey": ["pubkey_is_existing_validator"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
MODEL = Path(__file__).parent / "models" / "handler_deposit_request.mzn"


def _nfaults(_r: dict) -> int:
    return 0  # no failing gates in this handler


PROFILES = {
    "onewise": (ALL_ASPECTS, 1, None),
    "pairwise": (ALL_ASPECTS, 2, None),
    "standard": (ALL_ASPECTS, 2, None),
}


def build_profile(recs, name):
    if name == "all":
        return len(recs), recs
    aspects, t, filt = PROFILES[name]
    return cover(recs, aspects, t, filt)


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)


def materialize_profile(name: str, output_dir: Path | None = None) -> int:
    from eth_consensus_specs.gloas import minimal as spec
    _, chosen = build_profile(_recs(), name)
    reps = [SimpleNamespace(**r) for r in chosen]
    out = output_dir or (Path(__file__).parent / "reftests")
    return DepositRequestMaterializer(spec, MODEL).materialize_reps(out, reps)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    materialize = "--materialize" in sys.argv
    recs = _recs()
    print(f"distinct aspect-state signatures: {len(recs)}\n")

    if not args:
        print(f"{'profile':10} {'obligations':>12} {'cases':>7}")
        for name in ("onewise", "pairwise"):
            n_obl, chosen = build_profile(recs, name)
            print(f"{name:10} {n_obl:>12} {len(chosen):>7}")
        return 0

    n_obl, chosen = build_profile(recs, args[0])
    print(f"profile '{args[0]}': {len(chosen)} cases covering {n_obl} obligations")
    if materialize:
        materialize_profile(args[0])
        print("Validate with: python -m ...deposit_request.validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
