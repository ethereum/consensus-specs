"""Coverage declaration for Gloas ``process_parent_execution_payload``."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    constant,
    coverage_spec,
    dimension,
    exhaustive,
    Finite,
    fix,
    Integer,
    predicate,
    union,
)

from .observation import observe_attributes

CAPS = (
    ("withdrawals", "MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD", "REJECT_WITHDRAWALS_CAP"),
    ("consolidations", "MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD", "REJECT_CONSOLIDATIONS_CAP"),
    ("builder_deposits", "MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD", "REJECT_BUILDER_DEPOSITS_CAP"),
    ("builder_exits", "MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD", "REJECT_BUILDER_EXITS_CAP"),
)
counts = {field: attribute(f"observed_{field}_count", Integer(min=0)) for field, _, _ in CAPS}
limits = {field: constant(f"max_{field}", Integer(min=1)) for field, _, _ in CAPS}
revealed_input = attribute("observed_parent_payload_revealed", Boolean())
empty_input = attribute("observed_requests_empty", Boolean())
root_input = attribute("observed_requests_root_matches", Boolean())
deposit_input = attribute("observed_deposit_count", Integer(min=0))
settlement_input = attribute(
    "observed_payment_settlement", Finite(("CURRENT_EPOCH", "PREVIOUS_EPOCH", "EVICTED"))
)
value_input = attribute("observed_payment_value", Integer(min=0))
accepted_input = attribute("observed_accepted", Boolean())
effect_input = attribute("observed_state_effected", Boolean())
appended_input = attribute("observed_payment_withdrawal_appended", Boolean())
cleared_input = attribute("observed_payment_slot_cleared", Boolean())

revealed = dimension("parent_payload_revealed", revealed_input)
empty = dimension("requests_empty", empty_input)
root = dimension("requests_root_matches", root_input)
# These retain the legacy cap predicates' Boolean coverage; numeric counts
# and preset-bound limits independently determine the observed truth.
caps = tuple(
    dimension(f"{field}_within_cap", predicate(counts[field], limits[field], op="<="))
    for field, _, _ in CAPS
)
deposits = dimension("deposits_nonempty", deposit_input > 0)
settlement = dimension("payment_settlement", settlement_input)
nonzero = dimension("payment_value_nonzero", value_input > 0)
accepted = dimension("accepted", accepted_input)
effect = dimension("state_effected", effect_input)
appended = dimension("payment_withdrawal_appended", appended_input)
cleared = dimension("payment_slot_cleared", cleared_input)


def terminal_outcome(revealed, empty, root, caps, settlement, nonzero):
    return choose(
        (
            ~revealed,
            choose(empty, "EMPTY_PARENT_NOOP", no="REJECT_NONEMPTY_REQUESTS_FOR_EMPTY_PARENT"),
        ),
        (~root, "REJECT_REQUESTS_ROOT"),
        *((~cap, reject) for cap, (_, _, reject) in zip(caps, CAPS, strict=True)),
        (
            settlement == "CURRENT_EPOCH",
            choose(nonzero, "APPLY_CURRENT_WITH_WITHDRAWAL", no="APPLY_CURRENT_NO_WITHDRAWAL"),
        ),
        (
            settlement == "PREVIOUS_EPOCH",
            choose(nonzero, "APPLY_PREVIOUS_WITH_WITHDRAWAL", no="APPLY_PREVIOUS_NO_WITHDRAWAL"),
        ),
        choose(nonzero, "APPLY_EVICTED_WITH_WITHDRAWAL", no="APPLY_EVICTED_NO_WITHDRAWAL"),
    )


outcome = dimension(
    "outcome",
    terminal_outcome(
        revealed_input,
        empty_input,
        root_input,
        tuple(counts[field] <= limits[field] for field, _, _ in CAPS),
        settlement_input,
        value_input > 0,
    ),
)
DELIVERY = aspect("parent_delivery", revealed, empty, root)
CAPACITY = aspect("request_caps", *caps)
SHAPE = aspect("request_shape", deposits)
PAYMENT = aspect("payment", settlement, nonzero)
OUTCOME = aspect("outcome", outcome, accepted, effect, appended, cleared)
INPUT_ASPECTS = (DELIVERY, CAPACITY, SHAPE, PAYMENT)
ASPECTS = (*INPUT_ASPECTS, OUTCOME)
FACTORS = tuple(f for a in ASPECTS for f in a.declarations)
CAPS_PASS = {cap.name: True for cap in caps}
NORMAL_SCOPE = union(
    fix(parent_payload_revealed=False, requests_empty=True),
    fix(parent_payload_revealed=True, requests_root_matches=True, **CAPS_PASS),
)
NORMAL = union(
    *(a.exhaustive() * b.exhaustive() * NORMAL_SCOPE for a, b in combinations(INPUT_ASPECTS, 2)),
    OUTCOME.exhaustive() * NORMAL_SCOPE,
)
SINGLE_FAULT = union(
    fix(parent_payload_revealed=False, requests_empty=False, **CAPS_PASS),
    fix(parent_payload_revealed=True, requests_root_matches=False, **CAPS_PASS),
    *(
        fix(
            parent_payload_revealed=True,
            requests_root_matches=True,
            **{cap.name: cap.name != failed.name for cap in caps},
        )
        for failed in caps
    ),
)
# Reached-check flags are deterministic projections of this ordered input
# prefix. Covering the prefix with outcomes preserves their legacy obligations
# without adding six independent Boolean factors for redundant trace columns.
TRACE_INPUTS = exhaustive((revealed, empty, root, *caps))
EXCEPTIONAL = TRACE_INPUTS * OUTCOME.exhaustive() * SINGLE_FAULT
APPLIED = all_of(revealed, root, *caps)
COVERAGE = coverage_spec(
    "parent_execution_payload",
    focus="process_parent_execution_payload: delivery, request caps and dispatch, payment settlement, and effects",
    record="one operation",
    aspects=ASPECTS,
    constraints=(
        # Preserve the legacy fixture's shape: a nonempty deposits list also
        # populates all other lists; otherwise only over-cap lists are populated.
        empty == all_of(*caps, ~deposits),
        outcome == terminal_outcome(revealed, empty, root, caps, settlement, nonzero),
        accepted == (APPLIED | (~revealed & empty)),
        effect == APPLIED,
        appended == (APPLIED & nonzero),
        cleared == (APPLIED & (settlement != "EVICTED")),
    ),
    profiles={
        "smoke": exhaustive((outcome,)),
        "normal": NORMAL,
        "exceptional": EXCEPTIONAL,
        "standard": union(NORMAL, EXCEPTIONAL),
        "max": exhaustive(FACTORS),
    },
)

TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        f"max_{field}": lambda spec, name=name: int(getattr(spec, name)) for field, name, _ in CAPS
    },
)
