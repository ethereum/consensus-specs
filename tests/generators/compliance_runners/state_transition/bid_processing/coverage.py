"""Coverage profiles for process_execution_payload_bid (bid_processing aspect model).

Handler-specific instantiation of the generic combinatorial-over-aspects engine
in ``..aspect_coverage``: it declares this handler's aspects, coverage
dimensions, model, and a fault-count rank, then exposes named profiles.

Run:
    uv run python -m ...bid_processing.coverage                 # profile summary
    uv run python -m ...bid_processing.coverage standard --materialize
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from ..aspect_coverage import cover, dedup, enumerate_signatures
from .materializer import BidProcessingMaterializer, DIMS

# Input aspects (the bid_processing aggregate record dimensions).
INPUT_ASPECTS = {
    "builder_type": ["builder_type"],
    "bid_amount": ["cmp_bid_value_zero"],
    "signed_message": ["bid_signature"],
    "builder_funds": ["cmp_builder_balance_to_bid_value_plus_min_balance"],
    "blob_kzg_capacity": ["cmp_len_kzg_commitments_max_blobs"],
    "slot_epoch": ["cmp_state_slot_bid_slot"],
    "block_context": ["parent_block_hash_match", "parent_block_root_match",
                      "prev_randao_match"],
    # builder sub-aspect (from the aggregate record's builder field)
    "builder_version": ["payload_builder_version"],
    "builder_lifecycle": ["cmp_state_epoch_deposit_epoch", "cmp_state_epoch_withdrawal_epoch",
                           "cmp_finalized_epoch_deposit_epoch", "withdrawable_epoch_set"],
    "builder_balance": ["cmp_balance_zero", "cmp_balance_min_deposit"],
    "builder_pending_balance": ["has_pending_payments", "has_pending_withdrawals"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
MODEL = Path(__file__).parent / "models" / "handler_bid_processing.mzn"


def _nfaults(r: dict) -> int:
    """Failing applicable gates (mirrors the handler), for clean-rep tie-breaking."""
    f = 0
    is_self = r["builder_type"] == "SELF"
    if is_self:
        f += r["cmp_bid_value_zero"] == "GT"
        f += r["bid_signature"] != "INF"
    else:  # EXTERNAL
        f += r["cmp_finalized_epoch_deposit_epoch"] != "GT" or r["withdrawable_epoch_set"] != "F"
        f += r["payload_builder_version"] != "T"
        f += r["cmp_builder_balance_to_bid_value_plus_min_balance"] == "LT"
        f += r["bid_signature"] != "VALID"
    f += r["cmp_len_kzg_commitments_max_blobs"] not in ("LT", "EQ")
    f += r["cmp_state_slot_bid_slot"] != "EQ"
    f += not r["parent_block_hash_match"] == "T"
    f += r["parent_block_root_match"] != "T"
    f += not r["prev_randao_match"] == "T"
    return int(f)


# name -> (aspects, strength, outcome_filter)
PROFILES = {
    "onewise": (ALL_ASPECTS, 1, None),
    "pairwise": (ALL_ASPECTS, 2, None),
    "normal": (INPUT_ASPECTS, 2, "normal"),
    "exceptional": ({"builder_type": ["builder_type"], **OUTCOME_ASPECT}, 2, "exceptional"),
}


def build_profile(recs, name):
    if name == "standard":  # rich within accept, each rejection on each feasible branch
        _, normal = cover(recs, *PROFILES["normal"])
        _, exc = cover(recs, *PROFILES["exceptional"])
        return -1, dedup(normal + exc, ALL_ASPECTS)
    return cover(recs, *PROFILES[name])


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    materialize = "--materialize" in sys.argv

    print("Enumerating feasible space (~20s)...")
    recs = enumerate_signatures(MODEL, DIMS, ALL_ASPECTS, _nfaults)
    print(f"distinct aspect-state signatures: {len(recs)}\n")

    if not args:
        print(f"{'profile':14} {'obligations':>12} {'cases':>7}")
        for name in ("onewise", "normal", "exceptional"):
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
        from eth_consensus_specs.gloas import minimal as spec
        reps = [SimpleNamespace(**rec) for rec in chosen]
        out = Path(__file__).parent / "reftests"
        print()
        BidProcessingMaterializer(spec, MODEL).materialize_reps(out, reps)
        print("Validate with: python -m ...bid_processing.validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
