"""Coverage profiles for Gloas ``process_proposer_slashing``."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from ..aspect_coverage import cover, dedup, enumerate_signatures

from .materializer import _DIMS, ProposerSlashingMaterializer

INPUT_ASPECTS = {
    "headers": ["slots_match", "proposers_match", "headers_different"],
    "proposer_slashability": [
        "proposer_slashed",
        "proposer_activated",
        "proposer_withdrawable",
        "proposer_exited",
    ],
    "signatures": ["signature_1_valid", "signature_2_valid"],
    "pending_payment": ["payment_window", "payment_proposer_matches"],
}
OUTCOME_ASPECT = {"outcome": ["outcome", "pending_payment_cleared", "state_effected"]}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
ACCEPT = {
    "ACCEPT_CURRENT_PAYMENT_CLEARED",
    "ACCEPT_CURRENT_PAYMENT_RETAINED",
    "ACCEPT_PREVIOUS_PAYMENT_CLEARED",
    "ACCEPT_PREVIOUS_PAYMENT_RETAINED",
    "ACCEPT_OLD",
}
MODEL = Path(__file__).parent / "models" / "handler_proposer_slashing.mzn"


def _nfaults(r: dict) -> int:
    return (
        int(not r["slots_match"])
        + int(not r["proposers_match"])
        + int(not r["headers_different"])
        + int(r["proposer_slashed"])
        + int(not r["proposer_activated"])
        + int(r["proposer_withdrawable"])
        + int(r["signature_1_valid"] != "T")
        + int(r["signature_2_valid"] != "T")
    )


PROFILES = {
    "onewise": (ALL_ASPECTS, 1, None),
    "pairwise": (ALL_ASPECTS, 2, None),
    "normal": (INPUT_ASPECTS, 2, "normal"),
    "exceptional": (OUTCOME_ASPECT, 1, "exceptional"),
}


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)


def build_profile(recs, name):
    if name == "standard":
        _, normal = cover(recs, *PROFILES["normal"], accept=ACCEPT)
        _, exceptional = cover(recs, *PROFILES["exceptional"], accept=ACCEPT)
        return -1, dedup(normal + exceptional, ALL_ASPECTS)
    aspects, t, filt = PROFILES[name]
    return cover(recs, aspects, t, filt, accept=ACCEPT)


def materialize_profile(name: str) -> int:
    _, chosen = build_profile(_recs(), name)
    return ProposerSlashingMaterializer(spec, MODEL).materialize_reps(
        Path(__file__).parent / "reftests", [SimpleNamespace(**r) for r in chosen]
    )


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    materialize = "--materialize" in sys.argv
    recs = _recs()
    print(f"distinct aspect-state signatures: {len(recs)}\n")
    if not args:
        print(f"{'profile':14} {'obligations':>12} {'cases':>7}")
        for name in ("onewise", "normal", "exceptional"):
            obligations, cases = build_profile(recs, name)
            print(f"{name:14} {obligations:>12} {len(cases):>7}")
        _, cases = build_profile(recs, "standard")
        print(f"{'standard':14} {'(union)':>12} {len(cases):>7}")
        return 0
    obligations, cases = build_profile(recs, args[0])
    print(
        f"profile '{args[0]}': {len(cases)} cases"
        + (f" covering {obligations} obligations" if obligations >= 0 else "")
    )
    if materialize:
        materialize_profile(args[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
