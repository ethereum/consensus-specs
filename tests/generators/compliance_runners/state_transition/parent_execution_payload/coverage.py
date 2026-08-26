"""Coverage profiles for Gloas ``process_parent_execution_payload``."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS, ParentExecutionPayloadMaterializer

INPUT_ASPECTS = {
    "parent_delivery": [
        "parent_payload_revealed",
        "requests_empty",
        "requests_root_matches",
    ],
    "request_caps": [
        "withdrawals_within_cap",
        "consolidations_within_cap",
        "builder_deposits_within_cap",
        "builder_exits_within_cap",
    ],
    "request_shape": ["deposits_nonempty"],
    "payment": ["payment_settlement", "payment_value_nonzero"],
}
TRACE_ASPECT = {
    "trace": [
        "requests_empty_checked",
        "requests_root_checked",
        "withdrawals_cap_checked",
        "consolidations_cap_checked",
        "builder_deposits_cap_checked",
        "builder_exits_cap_checked",
    ]
}
OUTCOME_ASPECT = {
    "outcome": [
        "outcome",
        "state_effected",
        "payment_withdrawal_appended",
        "payment_slot_cleared",
        "dispatches_nonempty_requests",
    ]
}
ALL_ASPECTS = {**INPUT_ASPECTS, **TRACE_ASPECT, **OUTCOME_ASPECT}
MODEL = Path(__file__).parent / "models" / "handler_parent_execution_payload.mzn"


def _nfaults(record: dict) -> int:
    return (
        int(not record["requests_empty"] and not record["parent_payload_revealed"])
        + int(record["parent_payload_revealed"] and not record["requests_root_matches"])
        + int(not record["withdrawals_within_cap"])
        + int(not record["consolidations_within_cap"])
        + int(not record["builder_deposits_within_cap"])
        + int(not record["builder_exits_within_cap"])
    )


def _records():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)


def build_profile(records: list[dict], name: str):
    return _build_profile(
        records,
        name,
        ALL_ASPECTS,
        INPUT_ASPECTS,
        OUTCOME_ASPECT,
        normal_outcome_aspect=OUTCOME_ASPECT,
        exceptional_aspects={**TRACE_ASPECT, **OUTCOME_ASPECT},
    )


def materialize_profile(name: str, output_dir: Path | None = None) -> int:
    _, chosen = build_profile(_records(), name)
    reps = [SimpleNamespace(**record) for record in chosen]
    output_dir = output_dir or (Path(__file__).parent / "reftests")
    return ParentExecutionPayloadMaterializer(spec, MODEL).materialize_reps(output_dir, reps)
