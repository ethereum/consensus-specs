"""Coverage profiles for process_builder_exit_request.

Handler-specific instantiation of the shared ``..aspect_coverage`` engine —
the SAME engine execution_payload_bid uses. Two of the aspects
(builder_lifecycle, builder_pending_balance) are the shared aspect files bound
by both handlers.

Run:
    uv run python -m ...builder_exit_request.coverage                 # summary
    uv run python -m ...builder_exit_request.coverage standard --materialize
"""

from __future__ import annotations

from pathlib import Path

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS

INPUT_ASPECTS = {
    "builder_membership": ["builder_pubkey_found"],
    "builder_lifecycle": ["builder_deposit_to_finalized_epoch", "builder_withdrawable_epoch_set"],
    "builder_pending_balance": ["builder_has_pending_withdrawal", "builder_has_pending_payment"],
    "source_authorization": ["source_address_matches"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
MODEL = Path(__file__).parent / "models" / "handler_builder_exit_request.mzn"


def _nfaults(r: dict) -> int:
    if not r["builder_pubkey_found"]:
        return 1
    f = 0
    f += not r["builder_active"]
    f += r["source_address_matches"] != "T"
    f += r["builder_has_pending_balance"]
    return int(f)


def build_profile(name):
    return _build_profile(_recs(), name, ALL_ASPECTS, INPUT_ASPECTS, OUTCOME_ASPECT)


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)
