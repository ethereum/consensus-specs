"""Coverage profiles for the Gloas ``process_withdrawals`` handler.

Aspects follow the handler body: the parent guard, one aspect per stage of
``get_expected_withdrawals``, the pre-state bookkeeping the getter does not
determine, and one effect aspect per group of state updates.
"""

from __future__ import annotations

from pathlib import Path

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)
from tests.generators.compliance_runners.state_transition.withdrawals.materializer import (
    _DIMS,
)

INPUT_ASPECTS = {
    "parent": ["parent_payload_revealed"],
    "builder_pending": ["builder_pending_nonempty"],
    "pending_partial": ["pending_partial_nonempty"],
    "builder_sweep": ["builder_sweep_nonempty"],
    "validator_sweep": ["validator_sweep_nonempty"],
    "capacity": ["withdrawals_over_limit"],
}
EFFECT_ASPECTS = {
    "outcome": ["outcome"],
    "effects": ["state_effected"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
ALL_ASPECTS = {**INPUT_ASPECTS, **EFFECT_ASPECTS}
MODEL = Path(__file__).parent / "models" / "handler_withdrawals.mzn"


def _nfaults(record: dict) -> int:
    return 0


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)


def build_profile(name: str):
    return _build_profile(_recs(), name, ALL_ASPECTS, ALL_ASPECTS, OUTCOME_ASPECT)
