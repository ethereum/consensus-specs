"""Coverage profiles for Gloas ``process_payload_attestation``."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec

from ..aspect_coverage import cover, dedup, enumerate_signatures
from .materializer import PayloadAttestationMaterializer, _DIMS

INPUT_ASPECTS = {
    "block_context": ["parent_root_matches", "slot_is_previous"],
    "participants": ["attesting_indices_nonempty", "signature_valid"],
}
OUTCOME_ASPECT = {"outcome": ["outcome", "state_effected"]}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
MODEL = Path(__file__).parent / "models" / "handler_payload_attestation.mzn"


def _nfaults(r: dict) -> int:
    return (
        int(not r["parent_root_matches"])
        + int(not r["slot_is_previous"])
        + int(not r["attesting_indices_nonempty"])
        + int(r["signature_valid"] == "F")
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
    if name == "all":
        return len(recs), recs
    if name == "standard":
        _, normal = cover(recs, *PROFILES["normal"])
        _, exceptional = cover(recs, *PROFILES["exceptional"])
        return -1, dedup(normal + exceptional, ALL_ASPECTS)
    aspects, t, filt = PROFILES[name]
    return cover(recs, aspects, t, filt)


def materialize_profile(name: str, output_dir: Path | None = None) -> int:
    _, chosen = build_profile(_recs(), name)
    return PayloadAttestationMaterializer(spec, MODEL).materialize_reps(
        output_dir or (Path(__file__).parent / "reftests"), [SimpleNamespace(**r) for r in chosen]
    )


def main() -> int:
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
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
