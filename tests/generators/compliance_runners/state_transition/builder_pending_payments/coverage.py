from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    cover,
    enumerate_signatures,
)

from .materializer import _DIMS, BuilderPendingPaymentsMaterializer

MODEL = Path(__file__).parent / "models" / "handler_builder_pending_payments.mzn"
ASPECTS = {
    "previous_section": ["previous_epoch_occupancy", "mixed_quorum_relations"],
    "quorum": ["target_weight_to_quorum", "qualifying_payment_count"],
    "withdrawal": ["target_amount_nonzero"],
    "retained_section": ["next_epoch_payments_nondefault"],
    "existing_output": ["preexisting_withdrawals_nonempty"],
    "effects": ["withdrawals_appended", "state_effected", "outcome"],
}


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ASPECTS)


def build_profile(records, name):
    if name == "all":
        return len(records), records
    return cover(records, ASPECTS, 1 if name == "onewise" else 2)


def materialize_profile(name: str, output_dir: Path | None = None) -> int:
    _, chosen = build_profile(_recs(), name)
    return BuilderPendingPaymentsMaterializer(spec).materialize_reps(
        output_dir or (Path(__file__).parent / "reftests"), [SimpleNamespace(**r) for r in chosen]
    )
