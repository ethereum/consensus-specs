"""Coverage profiles for Gloas ``process_parent_execution_payload``."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    cover,
    dedup,
    enumerate_signatures,
)
from tests.generators.compliance_runners.state_transition.parent_execution_payload.materializer import (
    _DIMS,
    ParentExecutionPayloadMaterializer,
)

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
ACCEPT = {
    "EMPTY_PARENT_NOOP",
    "APPLY_CURRENT_WITH_WITHDRAWAL",
    "APPLY_CURRENT_NO_WITHDRAWAL",
    "APPLY_PREVIOUS_WITH_WITHDRAWAL",
    "APPLY_EVICTED_WITH_WITHDRAWAL",
    "APPLY_EVICTED_NO_WITHDRAWAL",
}
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
    if name == "all":
        return len(records), records
    if name == "standard":
        _, normal = cover(records, INPUT_ASPECTS, 2, "normal", accept=ACCEPT)
        _, normal_outcomes = cover(records, OUTCOME_ASPECT, 1, "normal", accept=ACCEPT)
        _, exceptional = cover(
            records,
            {**TRACE_ASPECT, **OUTCOME_ASPECT},
            1,
            "exceptional",
            accept=ACCEPT,
        )
        return -1, dedup(normal + normal_outcomes + exceptional, ALL_ASPECTS)
    if name == "onewise":
        return cover(records, ALL_ASPECTS, 1, accept=ACCEPT)
    if name == "pairwise":
        return cover(records, ALL_ASPECTS, 2, accept=ACCEPT)
    raise ValueError(f"unknown profile: {name}")


def materialize_profile(name: str, output_dir: Path | None = None) -> int:
    _, chosen = build_profile(_records(), name)
    reps = [SimpleNamespace(**record) for record in chosen]
    output_dir = output_dir or (Path(__file__).parent / "reftests")
    return ParentExecutionPayloadMaterializer(spec, MODEL).materialize_reps(output_dir, reps)
