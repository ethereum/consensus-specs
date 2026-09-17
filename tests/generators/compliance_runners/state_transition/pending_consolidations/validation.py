"""Independent semantic validation for pending-consolidation vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspects.base import _to_cmp
from tests.generators.compliance_runners.state_transition.provider import check_dimensions, decode

if TYPE_CHECKING:
    from pathlib import Path

    from tests.generators.compliance_runners.state_transition.provider import Check


_YAML = YAML(typ="safe")


def _status(state: Any, pending: Any, next_epoch: Any) -> str:
    source = state.validators[pending.source_index]
    if source.slashed:
        return "SLASHED"
    if source.withdrawable_epoch > next_epoch:
        return "BLOCKED"
    return "PROCESSABLE"


def recover_dimensions(pre: Any) -> dict[str, Any]:
    pending = list(pre.pending_consolidations)
    if not pending:
        return {
            "queue_layout": "EMPTY",
            "source_balance_to_effective": "NA",
            "outcome": "EMPTY_QUEUE",
        }

    next_epoch = spec.Epoch(spec.get_current_epoch(pre) + 1)
    statuses = [_status(pre, item, next_epoch) for item in pending]
    processable = next(
        (
            item
            for item, status in zip(pending, statuses, strict=True)
            if status == "PROCESSABLE"
        ),
        None,
    )
    relation = "NA"
    if processable is not None:
        source_index = processable.source_index
        relation = _to_cmp(
            pre.balances[source_index], pre.validators[source_index].effective_balance
        ).name

    layouts = {
        (): "EMPTY",
        ("SLASHED",): "SLASHED_ONLY",
        ("BLOCKED",): "BLOCKED_ONLY",
        ("PROCESSABLE",): "PROCESS_ONE",
        ("SLASHED", "PROCESSABLE"): "SLASHED_THEN_PROCESS",
        ("PROCESSABLE", "BLOCKED"): "PROCESS_THEN_BLOCKED",
    }
    layout = layouts.get(tuple(statuses), "INVALID_LAYOUT")
    outcome = {
        "EMPTY": "EMPTY_QUEUE",
        "SLASHED_ONLY": "SKIPPED_SLASHED",
        "BLOCKED_ONLY": "STOP_NOT_WITHDRAWABLE",
        "PROCESS_ONE": "PROCESSED",
        "SLASHED_THEN_PROCESS": "PROCESSED",
        "PROCESS_THEN_BLOCKED": "PROCESSED_THEN_STOPPED",
    }.get(layout, "INVALID_OUTCOME")
    return {
        "queue_layout": layout,
        "source_balance_to_effective": relation,
        "outcome": outcome,
    }


def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    return check_dimensions(claimed, recover_dimensions(pre))
