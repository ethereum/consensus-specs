"""Coverage declaration for Gloas ``process_pending_deposits``."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    any_of,
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    cmp3,
    coverage_spec,
    coverage_value,
    dimension,
    exhaustive,
    Finite,
    implies,
    Integer,
    union,
)

from .observation import observe_attributes

LAYOUTS = (
    "EMPTY",
    "FIRST_UNFINALIZED",
    "SINGLE",
    "POSTPONE_THEN_ACTIVE",
    "ACTIVE_THEN_UNFINALIZED",
    "LIMIT_AFTER_WITHDRAWN",
    "TWO_PROCESSABLE",
    "INVALID_THEN_PROCESSABLE",
)
ROLES = ("ACTIVE", "EXITING", "WITHDRAWN", "NEW_VALID", "NEW_INVALID", "ROLE_NA")
OUTCOMES = (
    "EMPTY_QUEUE",
    "STOP_UNFINALIZED",
    "STOP_PER_EPOCH_LIMIT",
    "STOP_CHURN_LIMIT",
    "PROCESSED",
)
layout_input = attribute("observed_queue_layout", Finite(LAYOUTS))
role_input = attribute("observed_primary_role", Finite(ROLES))
found_input = attribute("observed_validator_pubkey_found", Boolean())
active_input = attribute("observed_validator_active", Boolean())
exiting_input = attribute("observed_validator_exiting", Boolean())
signature_input = attribute("observed_deposit_signature_valid", Boolean())
withdrawable_input = attribute("observed_withdrawable_epoch", Integer(min=0))
next_epoch_input = attribute("observed_next_epoch", Integer(min=1))
carry_input = attribute("observed_initial_churn", Integer(min=0))
amount_input = attribute("observed_primary_amount", Integer(min=0))
available_input = attribute("observed_available_churn", Integer(min=1))
second_input = attribute("observed_second_amount", Integer(min=0))
remaining_input = attribute("observed_remaining_churn", Integer())
retained_input = attribute("observed_churn_retained", Boolean())
outcome_input = attribute("observed_outcome", Finite(OUTCOMES))

layout = dimension("queue_layout", layout_input)
role = dimension("primary_role", role_input)


def role_in(*values):
    # Activation is expressed as conjunctions of categorical exclusions.
    return all_of(*(role != value for value in ROLES if value not in values))


def layout_in(*values):
    return all_of(*(layout != value for value in LAYOUTS if value not in values))


secondary = dimension(
    "secondary_role",
    choose(
        (layout_input == "POSTPONE_THEN_ACTIVE", "SECOND_ACTIVE"),
        (layout_input == "ACTIVE_THEN_UNFINALIZED", "SECOND_UNFINALIZED"),
        (
            (layout_input == "TWO_PROCESSABLE") | (layout_input == "INVALID_THEN_PROCESSABLE"),
            "SECOND_PROCESSABLE",
        ),
        "SECOND_NONE",
    ),
)
reached = dimension(
    "primary_reached",
    (layout_input != "EMPTY")
    & (layout_input != "FIRST_UNFINALIZED")
    & (layout_input != "LIMIT_AFTER_WITHDRAWN"),
)
found = dimension("validator_pubkey_found", found_input)
active = dimension("validator_active", active_input, when=found)
exiting = dimension("validator_exiting", exiting_input, when=found)
signature = dimension(
    "deposit_signature_valid",
    signature_input,
    when=role_in("NEW_VALID", "NEW_INVALID"),
)
withdrawable = dimension(
    "withdrawable_epoch_to_next_epoch",
    cmp3(withdrawable_input, next_epoch_input, op="<"),
    when=role_in("EXITING", "WITHDRAWN"),
)
carry = dimension("initial_churn", choose(carry_input > 0, "CARRY_NONZERO", no="CARRY_ZERO"))
amount = dimension(
    "primary_amount_to_available",
    cmp3(amount_input, available_input, op="<="),
    when=role_in("ACTIVE", "NEW_VALID", "NEW_INVALID"),
)
second = dimension(
    "second_amount_to_remaining",
    cmp3(second_input, remaining_input, op="<="),
    when=layout_in("TWO_PROCESSABLE", "INVALID_THEN_PROCESSABLE"),
)
effect = dimension("churn_effect", choose(retained_input, "CHURN_RETAINED", no="CHURN_CLEARED"))
outcome = dimension("outcome", outcome_input)

QUEUE = aspect("queue_layout", layout, secondary, reached)
VALIDATOR = aspect("validator_state", role, found, active, exiting, withdrawable)
SIGNATURE = aspect("deposit_signature", signature)
CHURN = aspect("churn", carry, amount, second, effect)
OUTCOME = aspect("outcome", outcome)
ASPECTS = (QUEUE, VALIDATOR, SIGNATURE, CHURN, OUTCOME)
FACTORS = tuple(f for a in ASPECTS for f in a.declarations)
# Preserve the former triple-wise composite aspects, carrying applicability
# context even for projections whose conditional dimensions are absent.
PROJECTIONS = (
    exhaustive((layout, secondary)),
    exhaustive((reached,)),
    VALIDATOR.exhaustive(),
    exhaustive((role, signature)),
    exhaustive((carry,)),
    exhaustive((role, amount)),
    exhaustive((layout, second)),
    exhaustive((effect,)),
    OUTCOME.exhaustive(),
)
NORMAL = union(*(a * b * c for a, b, c in combinations(PROJECTIONS, 3)))
TWO = (layout == "TWO_PROCESSABLE") | (layout == "INVALID_THEN_PROCESSABLE")
WITHDRAWING = (role == "EXITING") | (role == "WITHDRAWN")
CHARGED = (role == "ACTIVE") | (role == "NEW_VALID") | (role == "NEW_INVALID")
COVERAGE = coverage_spec(
    "pending_deposits",
    focus="process_pending_deposits: queue order, lifecycle, finality, limits, and activation churn",
    record="one epoch-processing step",
    aspects=ASPECTS,
    constraints=(
        (layout == "EMPTY") == (role == "ROLE_NA"),
        implies(layout == "FIRST_UNFINALIZED", role != "ROLE_NA"),
        implies(
            (layout == "SINGLE")
            | (layout == "ACTIVE_THEN_UNFINALIZED")
            | (layout == "TWO_PROCESSABLE"),
            (role == "ACTIVE") | (role == "NEW_VALID"),
        ),
        implies(layout == "INVALID_THEN_PROCESSABLE", role == "NEW_INVALID"),
        implies(layout == "POSTPONE_THEN_ACTIVE", role == "EXITING"),
        implies(layout == "LIMIT_AFTER_WITHDRAWN", role == "WITHDRAWN"),
        secondary
        == choose(
            (layout == "POSTPONE_THEN_ACTIVE", "SECOND_ACTIVE"),
            (layout == "ACTIVE_THEN_UNFINALIZED", "SECOND_UNFINALIZED"),
            (TWO, "SECOND_PROCESSABLE"),
            "SECOND_NONE",
        ),
        reached
        == all_of(
            layout != "EMPTY", layout != "FIRST_UNFINALIZED", layout != "LIMIT_AFTER_WITHDRAWN"
        ),
        found == any_of(role == "ACTIVE", role == "EXITING", role == "WITHDRAWN"),
        implies(found, active == (role == "ACTIVE")),
        implies(found, exiting == WITHDRAWING),
        implies(role == "WITHDRAWN", withdrawable),
        implies(role == "EXITING", ~withdrawable),
        implies(
            (role == "NEW_VALID") | (role == "NEW_INVALID"), signature == (role == "NEW_VALID")
        ),
        implies(TWO, coverage_value(amount) == "LT"),
        outcome
        == choose(
            (layout == "FIRST_UNFINALIZED", "STOP_UNFINALIZED"),
            (layout == "LIMIT_AFTER_WITHDRAWN", "STOP_PER_EPOCH_LIMIT"),
            (layout == "EMPTY", "EMPTY_QUEUE"),
            (reached & CHARGED & (coverage_value(amount) == "GT"), "STOP_CHURN_LIMIT"),
            (layout == "ACTIVE_THEN_UNFINALIZED", "STOP_UNFINALIZED"),
            (TWO & (coverage_value(second) == "GT"), "STOP_CHURN_LIMIT"),
            "PROCESSED",
        ),
        effect == choose(outcome == "STOP_CHURN_LIMIT", "CHURN_RETAINED", no="CHURN_CLEARED"),
    ),
    profiles={
        "smoke": OUTCOME.exhaustive(),
        "normal": NORMAL,
        "standard": NORMAL,
        "max": exhaustive(FACTORS),
    },
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes)
