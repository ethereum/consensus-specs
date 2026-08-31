"""Coverage profiles for Gloas ``process_attestation``."""

from __future__ import annotations

from pathlib import Path

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS

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
MODEL = Path(__file__).parent / "models" / "handler_attestation.mzn"


def _nfaults(r: dict) -> int:
    # Count independent failing checks. Structural checks are a dependency
    # chain: later checks are not applicable when an earlier check already
    # prevents the attestation from being indexed and processed.
    faults = int(not r["target_epoch_in_window"])
    if r["target_epoch_in_window"]:
        faults += int(not r["target_epoch_matches_slot"])
    faults += int(not r["inclusion_delay_ok"])
    faults += int(not r["index_valid"])
    if r["index_valid"]:
        faults += int(not r["committee_indices_valid"])
        if r["committee_indices_valid"]:
            faults += int(not r["committee_nonempty"])
            if r["committee_nonempty"]:
                faults += int(not r["aggregation_length_valid"])
                if r["aggregation_length_valid"]:
                    faults += int(not r["signature_valid"])
    return faults


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)


def build_profile(name):
    return _build_profile(
        _recs(),
        name,
        ALL_ASPECTS,
        INPUT_ASPECTS,
        OUTCOME_ASPECT,
        normal_outcome_aspect=OUTCOME_ASPECT,
    )
