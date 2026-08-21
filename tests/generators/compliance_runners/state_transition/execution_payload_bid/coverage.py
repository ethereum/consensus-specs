"""Coverage profiles for process_execution_payload_bid.

Handler-specific instantiation of the generic combinatorial-over-aspects engine
in ``..aspect_coverage``: it declares this handler's aspects, coverage
dimensions, model, and a fault-count rank, then exposes named profiles.

Run:
    uv run python -m ...execution_payload_bid.coverage                 # profile summary
    uv run python -m ...execution_payload_bid.coverage standard --materialize
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from ..aspect_coverage import cover, dedup, enumerate_signatures
from .materializer import ExecutionPayloadBidMaterializer, _DIMS

# Fine-grained input aspects (realization + the handler-local bid amount).
#
# Keep these available for the detailed profile.  The default profiles below
# use the coarser logical groups, where the dimensions in each group form one
# composite factor for pairwise coverage.
FINE_INPUT_ASPECTS = {
    "entity_reference": ["builder_ref"],
    "builder_lifecycle": ["builder_deposit_to_finalized_epoch", "builder_withdrawable_epoch_set"],
    "builder_version": ["builder_version_valid"],
    "builder_pending_balance": ["builder_has_pending_withdrawal", "builder_has_pending_payment"],
    "builder_funds": ["builder_balance_to_min_balance", "builder_available_to_bid"],
    "signed_message": ["builder_signature_valid"],
    "self_build_signature": ["self_build_signature_is_infinity"],
    "bid_amount": ["amount_positive"],
    "blob_kzg_capacity": ["bid_kzg_to_max"],
    "slot_epoch": ["bid_slot_to_state", "state_slot_past_genesis"],
    "block_context": ["bid_parent_block_hash_matches", "bid_parent_block_root_matches",
                      "bid_prev_randao_matches"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}

# A complete builder/state tuple participates in pairwise joins with every
# other aspect.  This is intentionally a tuple-valued aspect rather than a
# new MiniZinc predicate: the handler still constrains each realization
# dimension independently and aspect_coverage.py joins their feasible values.
INPUT_ASPECTS = {
    "builder_state": [
        "builder_ref",
        "builder_deposit_to_finalized_epoch",
        "builder_withdrawable_epoch_set",
        "builder_version_valid",
        "builder_has_pending_withdrawal",
        "builder_has_pending_payment",
        "builder_balance_to_min_balance",
        "builder_available_to_bid",
    ],
    "signed_message": ["builder_signature_valid"],
    "self_build_signature": ["self_build_signature_is_infinity"],
    "bid_amount": ["amount_positive"],
    "beacon_context": [
        "bid_kzg_to_max",
        "bid_slot_to_state",
        "state_slot_past_genesis",
        "bid_parent_block_hash_matches",
        "bid_parent_block_root_matches",
        "bid_prev_randao_matches",
    ],
}

FINE_ALL_ASPECTS = {**FINE_INPUT_ASPECTS, **OUTCOME_ASPECT}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
MODEL = Path(__file__).parent / "models" / "handler_execution_payload_bid.mzn"


def _nfaults(r: dict) -> int:
    """Failing applicable gates (mirrors the handler), for clean-rep tie-breaking."""
    f = 0
    if r["self_build"]:
        f += r["amount_positive"]
        f += r["self_build_signature_is_infinity"] != "T"
    elif r["builder_ref"] == "NON_EXISTING":
        f += 1
    elif r["builder_ref"] == "EXISTING":
        f += not r["builder_active"]
        f += r["builder_version_valid"] != "T"
        f += not r["builder_can_cover_bid"]
        f += r["builder_signature_valid"] != "T"
    f += r["bid_kzg_to_max"] not in ("LT", "EQ")
    f += r["bid_slot_to_state"] != "EQ"
    f += not r["state_slot_past_genesis"]
    f += not r["bid_parent_block_hash_matches"]
    f += r["bid_parent_block_root_matches"] == "F"
    f += not r["bid_prev_randao_matches"]
    return int(f)


# name -> (aspects, strength, outcome_filter)
PROFILES = {
    "onewise": (ALL_ASPECTS, 1, None),
    "pairwise": (ALL_ASPECTS, 2, None),
    "normal": (INPUT_ASPECTS, 2, "normal"),
    "exceptional": ({"builder_state": INPUT_ASPECTS["builder_state"], **OUTCOME_ASPECT}, 2, "exceptional"),
    "detailed": (FINE_ALL_ASPECTS, 2, None),
}


def build_profile(recs, name):
    if name == "all":
        return len(recs), recs
    if name == "standard":  # rich within accept, each rejection on each feasible branch
        _, normal = cover(recs, *PROFILES["normal"])
        _, exc = cover(recs, *PROFILES["exceptional"])
        return -1, dedup(normal + exc, ALL_ASPECTS)
    return cover(recs, *PROFILES[name])


def _materialize(recs, name: str) -> int:
    _, chosen = build_profile(recs, name)
    from eth_consensus_specs.gloas import minimal as spec

    reps = [SimpleNamespace(**rec) for rec in chosen]
    out = Path(__file__).parent / "reftests"
    return ExecutionPayloadBidMaterializer(spec, MODEL).materialize_reps(out, reps)


def materialize_profile(name: str) -> int:
    recs = enumerate_signatures(MODEL, _DIMS, FINE_ALL_ASPECTS, _nfaults)
    return _materialize(recs, name)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    materialize = "--materialize" in sys.argv

    print("Enumerating feasible space (~20s)...")
    # Preserve the fine-grained signature space so that both coarse and
    # detailed profiles can be selected from the same enumeration.
    recs = enumerate_signatures(MODEL, _DIMS, FINE_ALL_ASPECTS, _nfaults)
    print(f"distinct aspect-state signatures: {len(recs)}\n")

    if not args:
        print(f"{'profile':14} {'obligations':>12} {'cases':>7}")
        for name in ("onewise", "normal", "exceptional", "detailed"):
            n_obl, chosen = build_profile(recs, name)
            print(f"{name:14} {n_obl:>12} {len(chosen):>7}")
        _, std = build_profile(recs, "standard")
        print(f"{'standard':14} {'(union)':>12} {len(std):>7}")
        print("\n(also: coverage pairwise --materialize)")
        return 0

    n_obl, chosen = build_profile(recs, args[0])
    print(f"profile '{args[0]}': {len(chosen)} cases"
          + (f" covering {n_obl} obligations" if n_obl >= 0 else ""))
    if materialize:
        print()
        _materialize(recs, args[0])
        print("Validate with: python -m ...execution_payload_bid.validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
