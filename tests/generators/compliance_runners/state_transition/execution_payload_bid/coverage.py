"""Coverage profiles for process_execution_payload_bid.

Handler-specific instantiation of the generic combinatorial-over-aspects engine
in ``..aspect_coverage``: it declares this handler's aspects, coverage
dimensions, model, and a fault-count rank, then exposes named profiles.

Run:
    uv run python -m ...execution_payload_bid.coverage                 # profile summary
    uv run python -m ...execution_payload_bid.coverage standard --materialize
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS, ExecutionPayloadBidMaterializer

# Fine-grained input aspects (realization + the handler-local bid amount).
# The dimensions remain part of the signature used by `all`. The normal and
# exceptional profiles use coarser logical groups, where dimensions in each
# group form one composite factor for coverage.
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
    "block_context": [
        "bid_parent_block_hash_matches",
        "bid_parent_block_root_matches",
        "bid_prev_randao_matches",
    ],
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


def build_profile(recs, name):
    return _build_profile(
        recs,
        name,
        ALL_ASPECTS,
        INPUT_ASPECTS,
        OUTCOME_ASPECT,
        exceptional_aspects={"builder_state": INPUT_ASPECTS["builder_state"], **OUTCOME_ASPECT},
        exceptional_t=2,
    )


def _materialize(recs, name: str, output_dir: Path | None = None) -> int:
    _, chosen = build_profile(recs, name)
    reps = [SimpleNamespace(**rec) for rec in chosen]
    out = output_dir or (Path(__file__).parent / "reftests")
    return ExecutionPayloadBidMaterializer(spec).materialize_reps(out, reps)


def materialize_profile(name: str, output_dir: Path | None = None) -> int:
    recs = enumerate_signatures(MODEL, _DIMS, FINE_ALL_ASPECTS, _nfaults)
    return _materialize(recs, name, output_dir)
