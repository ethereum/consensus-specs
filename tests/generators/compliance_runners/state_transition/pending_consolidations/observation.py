"""Observe queue layout and transfer relations from a pre-state."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
        Context,
    )

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import NA


def _status(state, pending, next_epoch) -> str:
    source = state.validators[pending.source_index]
    if source.slashed:
        return "SLASHED"
    if source.withdrawable_epoch > next_epoch:
        return "BLOCKED"
    return "PROCESSABLE"


def observe_attributes(ctx: Context) -> dict[str, Any]:
    spec, state = ctx.spec, ctx.pre
    pending = list(state.pending_consolidations)
    if not pending:
        return {
            "observed_queue_layout": "EMPTY",
            "source_balance": NA,
            "effective_balance": NA,
            "observed_outcome": "EMPTY_QUEUE",
        }

    next_epoch = spec.Epoch(spec.get_current_epoch(state) + 1)
    statuses = [_status(state, item, next_epoch) for item in pending]
    layouts = {
        ("SLASHED",): "SLASHED_ONLY",
        ("BLOCKED",): "BLOCKED_ONLY",
        ("PROCESSABLE",): "PROCESS_ONE",
        ("SLASHED", "PROCESSABLE"): "SLASHED_THEN_PROCESS",
        ("PROCESSABLE", "BLOCKED"): "PROCESS_THEN_BLOCKED",
    }
    layout = layouts.get(tuple(statuses), "INVALID_LAYOUT")
    processable = next(
        (item for item, status in zip(pending, statuses, strict=True) if status == "PROCESSABLE"),
        None,
    )
    source_balance = NA
    effective_balance = NA
    if processable is not None:
        source_index = int(processable.source_index)
        source_balance = int(state.balances[source_index])
        effective_balance = int(state.validators[source_index].effective_balance)
    outcome = {
        "SLASHED_ONLY": "SKIPPED_SLASHED",
        "BLOCKED_ONLY": "STOP_NOT_WITHDRAWABLE",
        "PROCESS_ONE": "PROCESSED",
        "SLASHED_THEN_PROCESS": "PROCESSED",
        "PROCESS_THEN_BLOCKED": "PROCESSED_THEN_STOPPED",
    }.get(layout, "INVALID_OUTCOME")
    return {
        "observed_queue_layout": layout,
        "source_balance": source_balance,
        "effective_balance": effective_balance,
        "observed_outcome": outcome,
    }
