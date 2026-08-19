"""Coverage profiles for process_consolidation_request.

Handler-specific instantiation of the shared ``..aspect_coverage`` engine.
Reuses the validator family for the SOURCE validator + source_authorization, and
a compact target_validator aspect for the target.

Run:
    uv run python -m ...consolidation_request.coverage
    uv run python -m ...consolidation_request.coverage standard --materialize
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from ..aspect_coverage import cover, dedup, enumerate_signatures
from .materializer import ConsolidationRequestMaterializer, _DIMS

# Fine-grained input aspects. These remain available through the detailed
# profile; the default profiles use the composite validator_state factor.
FINE_INPUT_ASPECTS = {
    "consolidation_pair": ["same_source_target"],
    "pending_consolidations_capacity": ["pending_consolidations_full"],
    "consolidation_churn": ["sufficient_consolidation_churn"],
    "validator_membership": ["validator_pubkey_found"],
    "validator_credential": ["validator_credential"],
    "source_authorization": ["source_address_matches"],
    "validator_lifecycle": ["validator_active", "validator_exiting", "validator_old_enough"],
    "validator_pending_withdrawal": ["has_pending_partial_withdrawal"],
    "target_validator": ["target_found", "target_credential", "target_active", "target_exiting"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
INPUT_ASPECTS = {
    "consolidation_pair": ["same_source_target"],
    "pending_consolidations_capacity": ["pending_consolidations_full"],
    "consolidation_churn": ["sufficient_consolidation_churn"],
    "validator_state": [
        "validator_pubkey_found",
        "validator_credential",
        "source_address_matches",
        "validator_active",
        "validator_exiting",
        "validator_old_enough",
        "has_pending_partial_withdrawal",
        "target_found",
        "target_credential",
        "target_active",
        "target_exiting",
    ],
}
FINE_ALL_ASPECTS = {**FINE_INPUT_ASPECTS, **OUTCOME_ASPECT}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
ACCEPT = {"SWITCHED_TO_COMPOUNDING", "CONSOLIDATED"}
MODEL = Path(__file__).parent / "models" / "handler_consolidation_request.mzn"


def _nfaults(r: dict) -> int:
    return 0 if r["outcome"] in ACCEPT else 1


PROFILES = {
    "onewise": (ALL_ASPECTS, 1, None),
    "pairwise": (ALL_ASPECTS, 2, None),
    "normal": (INPUT_ASPECTS, 2, "normal"),
    "exceptional": (OUTCOME_ASPECT, 1, "exceptional"),
    "detailed": (FINE_ALL_ASPECTS, 2, None),
}


def build_profile(recs, name):
    if name == "all":
        return len(recs), recs
    if name == "standard":
        _, normal = cover(recs, *PROFILES["normal"], accept=ACCEPT)
        _, exc = cover(recs, *PROFILES["exceptional"], accept=ACCEPT)
        return -1, dedup(normal + exc, ALL_ASPECTS)
    aspects, t, filt = PROFILES[name]
    return cover(recs, aspects, t, filt, accept=ACCEPT)


def _recs():
    return enumerate_signatures(MODEL, _DIMS, FINE_ALL_ASPECTS, _nfaults)


def materialize_profile(name: str) -> int:
    from eth_consensus_specs.gloas import minimal as spec
    _, chosen = build_profile(_recs(), name)
    reps = [SimpleNamespace(**r) for r in chosen]
    out = Path(__file__).parent / "reftests"
    return ConsolidationRequestMaterializer(spec, MODEL).materialize_reps(out, reps)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    materialize = "--materialize" in sys.argv
    recs = _recs()
    print(f"distinct aspect-state signatures: {len(recs)}\n")

    if not args:
        print(f"{'profile':14} {'obligations':>12} {'cases':>7}")
        for name in ("onewise", "normal", "exceptional", "detailed", "all"):
            n_obl, chosen = build_profile(recs, name)
            print(f"{name:14} {n_obl:>12} {len(chosen):>7}")
        _, std = build_profile(recs, "standard")
        print(f"{'standard':14} {'(union)':>12} {len(std):>7}")
        return 0

    n_obl, chosen = build_profile(recs, args[0])
    print(f"profile '{args[0]}': {len(chosen)} cases"
          + (f" covering {n_obl} obligations" if n_obl >= 0 else ""))
    if materialize:
        materialize_profile(args[0])
        print("Validate with: python -m ...consolidation_request.validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
