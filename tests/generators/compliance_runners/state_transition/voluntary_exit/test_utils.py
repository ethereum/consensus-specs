"""Canonical witness helpers shared by voluntary-exit tests."""

from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    materializer_record,
)

from .target import TARGET


def make_record(spec, **overrides):
    target = TARGET.for_spec(spec)
    assignment = {
        "activation_le_current": True,
        "current_lt_exit": True,
        "exit_not_initiated": True,
        "current_ge_message_epoch": "EQ",
        "current_ge_seasoned": "GT_1",
        "pending_balance_zero": True,
        "matching_pending_entries": "ZERO",
        "foreign_pending_entries": "ZERO",
        "signature_ok": True,
        "earliest_lt_new": True,
        "balance_gt_consumable": "LT_FAR",
        **overrides,
    }
    assignment["accepted"] = target.assertion_result(assignment).expected_accepted
    return materializer_record(target, assignment)


CHURN_CASES = [
    ("NEW_EPOCH", "LT_FAR", "ZERO"),
    ("NEW_EPOCH", "EQ", "ZERO"),
    ("NEW_EPOCH", "GT_FAR", "ONE"),
    ("NEW_EPOCH", "GT_FAR", "MANY"),
    ("CARRIED_AVAILABLE", "LT_FAR", "ZERO"),
    ("CARRIED_AVAILABLE", "LT_1", "ZERO"),
    ("CARRIED_AVAILABLE", "EQ", "ZERO"),
    ("CARRIED_EXHAUSTED", "GT_1", "ONE"),
    ("CARRIED_EXHAUSTED", "GT_FAR", "ONE"),
    ("CARRIED_EXHAUSTED", "GT_FAR", "MANY"),
]
