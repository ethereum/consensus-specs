"""Coverage declaration for Gloas ``process_pending_consolidations``."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    cmp3,
    coverage_spec,
    dimension,
    exhaustive,
    Finite,
    implies,
    Integer,
    union,
)

from .observation import observe_attributes

queue_layout_input = attribute(
    "observed_queue_layout",
    Finite(
        (
            "EMPTY",
            "SLASHED_ONLY",
            "BLOCKED_ONLY",
            "PROCESS_ONE",
            "SLASHED_THEN_PROCESS",
            "PROCESS_THEN_BLOCKED",
        )
    ),
)
source_balance = attribute("source_balance", Integer(min=0))
effective_balance = attribute("effective_balance", Integer(min=0))
outcome_input = attribute(
    "observed_outcome",
    Finite(
        (
            "EMPTY_QUEUE",
            "SKIPPED_SLASHED",
            "STOP_NOT_WITHDRAWABLE",
            "PROCESSED",
            "PROCESSED_THEN_STOPPED",
        )
    ),
)

QUEUE = aspect("queue", dimension("queue_layout", queue_layout_input))
TRANSFER = aspect(
    "transfer",
    dimension(
        "source_balance_to_effective",
        cmp3(source_balance, effective_balance),
        when=(
            (QUEUE.ref("queue_layout") != "EMPTY")
            & (QUEUE.ref("queue_layout") != "SLASHED_ONLY")
            & (QUEUE.ref("queue_layout") != "BLOCKED_ONLY")
        ),
    ),
)
OUTCOME = aspect("outcome", dimension("outcome", outcome_input))
ASPECTS = (QUEUE, TRANSFER, OUTCOME)

NORMAL = union(
    *(left.exhaustive() * right.exhaustive() for left, right in combinations(ASPECTS, 2))
)
ALL_FACTORS = tuple(f for aspect_ in ASPECTS for f in aspect_.declarations)
COVERAGE = coverage_spec(
    "pending_consolidations",
    focus="process_pending_consolidations: queue order, transfer balance, and outcome",
    record="one vector",
    aspects=ASPECTS,
    profiles={
        "smoke": OUTCOME.exhaustive(),
        "normal": NORMAL,
        "max": exhaustive(ALL_FACTORS),
        "standard": NORMAL,
    },
    constraints=(
        implies(QUEUE.ref("queue_layout") == "EMPTY", OUTCOME.ref("outcome") == "EMPTY_QUEUE"),
        implies(
            QUEUE.ref("queue_layout") == "SLASHED_ONLY",
            OUTCOME.ref("outcome") == "SKIPPED_SLASHED",
        ),
        implies(
            QUEUE.ref("queue_layout") == "BLOCKED_ONLY",
            OUTCOME.ref("outcome") == "STOP_NOT_WITHDRAWABLE",
        ),
        implies(
            (QUEUE.ref("queue_layout") == "PROCESS_ONE")
            | (QUEUE.ref("queue_layout") == "SLASHED_THEN_PROCESS"),
            OUTCOME.ref("outcome") == "PROCESSED",
        ),
        implies(
            QUEUE.ref("queue_layout") == "PROCESS_THEN_BLOCKED",
            OUTCOME.ref("outcome") == "PROCESSED_THEN_STOPPED",
        ),
    ),
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes, backend="python")
