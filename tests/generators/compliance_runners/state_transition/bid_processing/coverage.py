"""Coverage profiles for process_execution_payload_bid (bid_processing aspect model).

Handler-specific instantiation of the generic combinatorial-over-aspects engine
in ``..aspect_coverage``: it declares this handler's aspects, coverage
dimensions, model, and a fault-count rank, then exposes named profiles.

Run:
    uv run python -m ...bid_processing.coverage                 # profile summary
    uv run python -m ...bid_processing.coverage standard --materialize
"""

from __future__ import annotations

from pathlib import Path

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)
from tests.generators.compliance_runners.state_transition.bid_processing.materializer import (
    DIMS,
)

# Input aspects (the bid_processing aggregate record dimensions).
INPUT_ASPECTS = {
    "builder_type": ["builder_type"],
    "bid_amount": ["cmp_bid_value_zero"],
    "signed_message": ["bid_signature"],
    "builder_funds": ["cmp_builder_balance_to_bid_value_plus_min_balance"],
    "blob_kzg_capacity": ["cmp_len_kzg_commitments_max_blobs"],
    "slot_epoch": ["cmp_state_slot_bid_slot"],
    "block_context": ["parent_block_hash_match", "parent_block_root_match", "prev_randao_match"],
    # builder sub-aspect (from the aggregate record's builder field)
    "builder_version": ["payload_builder_version"],
    "builder_lifecycle": [
        "cmp_state_epoch_deposit_epoch",
        "cmp_state_epoch_withdrawal_epoch",
        "cmp_finalized_epoch_deposit_epoch",
        "withdrawable_epoch_set",
    ],
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
    f += r["parent_block_hash_match"] != "T"
    f += r["parent_block_root_match"] != "T"
    f += r["prev_randao_match"] != "T"
    return int(f)


def _recs():
    return enumerate_signatures(MODEL, DIMS, INPUT_ASPECTS, _nfaults)


def build_profile(name):
    return _build_profile(
        _recs(),
        name,
        ALL_ASPECTS,
        INPUT_ASPECTS,
        OUTCOME_ASPECT,
        # exceptional_aspects={"builder_state": INPUT_ASPECTS["builder_state"], **OUTCOME_ASPECT},
        # exceptional_t=2,
    )
