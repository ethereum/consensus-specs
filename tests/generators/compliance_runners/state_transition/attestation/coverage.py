"""Coverage profiles for Gloas ``process_attestation``."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec

from ..aspect_coverage import cover, dedup, enumerate_signatures
from .materializer import AttestationMaterializer, _DIMS

INPUT_ASPECTS = {
    "data": [
        "target_epoch_in_window",
        "target_epoch_matches_slot",
        "inclusion_delay_ok",
        "index_valid",
    ],
    "committees": ["committee_indices_valid", "committee_nonempty", "aggregation_length_valid"],
    "signature": ["signature_valid"],
    "builder_payment": [
        "attestation_is_same_slot",
        "pending_payment_amount_positive",
        "sets_new_participation_flag",
    ],
}
OUTCOME_ASPECT = {"outcome": ["target_is_current", "payment_weight_increased", "outcome"]}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
ACCEPT = {"ACCEPT_CURRENT", "ACCEPT_PREVIOUS"}
MODEL = Path(__file__).parent / "models" / "handler_attestation.mzn"


def _nfaults(r: dict) -> int:
    return sum(not r[n] for n in _DIMS[:8])


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)


def build_profile(recs, name):
    if name == "standard":
        _, normal_inputs = cover(recs, INPUT_ASPECTS, 2, "normal", accept=ACCEPT)
        _, normal_outcomes = cover(recs, OUTCOME_ASPECT, 1, "normal", accept=ACCEPT)
        _, exceptional = cover(recs, OUTCOME_ASPECT, 1, "exceptional", accept=ACCEPT)
        return -1, dedup(normal_inputs + normal_outcomes + exceptional, ALL_ASPECTS)
    if name == "onewise":
        return cover(recs, ALL_ASPECTS, 1, accept=ACCEPT)
    return cover(recs, ALL_ASPECTS, 2, accept=ACCEPT)


def materialize_profile(name: str) -> int:
    _, chosen = build_profile(_recs(), name)
    return AttestationMaterializer(spec, MODEL).materialize_reps(
        Path(__file__).parent / "reftests", [SimpleNamespace(**r) for r in chosen]
    )


def main() -> int:
    args, materialize = (
        [a for a in sys.argv[1:] if not a.startswith("--")],
        "--materialize" in sys.argv,
    )
    recs = _recs()
    if not args:
        for name in ("onewise", "standard"):
            obligations, cases = build_profile(recs, name)
            print(
                f"{name}: {len(cases)} cases"
                + (f", {obligations} obligations" if obligations >= 0 else "")
            )
        return 0
    _, cases = build_profile(recs, args[0])
    print(f"profile '{args[0]}': {len(cases)} cases")
    if materialize:
        materialize_profile(args[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
