"""Coverage declaration for Gloas ``process_withdrawal_request``."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    cmp3,
    constant,
    coverage_spec,
    coverage_value,
    dimension,
    exhaustive,
    Finite,
    fix,
    implies,
    Integer,
    union,
)

from .observation import observe_attributes


def boolean(name):
    return attribute(f"observed_{name}", Boolean())


full_input = boolean("is_full_exit_request")
found_input = boolean("validator_pubkey_found")
credential_input = attribute(
    "observed_validator_credential", Finite(("BLS", "ETH1", "COMPOUNDING", "BUILDER", "OTHER"))
)
address_input = boolean("source_address_matches")
active_input = boolean("validator_active")
exiting_input = boolean("validator_exiting")
old_input = boolean("validator_old_enough")
pending_input = boolean("has_pending_partial_withdrawal")
queue_input = attribute("observed_queue_length", Integer(min=0))
effective_input = attribute("observed_effective_balance", Integer(min=0))
balance_input = attribute("observed_balance", Integer(min=0))
required_input = attribute("observed_required_balance", Integer(min=1))
minimum = constant("minimum_activation_balance", Integer(min=1))
limit = constant("partial_withdrawals_limit", Integer(min=2))

full = dimension("is_full_exit_request", full_input)
queue = dimension(
    "partial_queue_capacity",
    choose((queue_input == 0, "EMPTY"), (queue_input == limit, "FULL"), "AVAILABLE"),
)
found = dimension("validator_pubkey_found", found_input)
credential = dimension("validator_credential", credential_input, when=found)
address = dimension("source_address_matches", address_input, when=found)
active = dimension("validator_active", active_input, when=found)
exiting = dimension("validator_exiting", exiting_input, when=found)
old = dimension("validator_old_enough", old_input, when=found)
pending = dimension("has_pending_partial_withdrawal", pending_input, when=found)
effective = dimension(
    "effective_balance_to_min_activation", cmp3(effective_input, minimum), when=found
)
balance = dimension("balance_to_required", cmp3(balance_input, required_input), when=found)
execution = found_input & ((credential_input == "ETH1") | (credential_input == "COMPOUNDING"))
compounding = found_input & (credential_input == "COMPOUNDING")


def result(
    full,
    queue_full,
    found,
    execution,
    compounding,
    address,
    active,
    exiting,
    old,
    pending,
    sufficient,
    excess,
):
    return choose(
        (queue_full & ~full, "REJECTED_QUEUE_FULL"),
        (~found, "REJECTED_NOT_FOUND"),
        (~(execution & address), "REJECTED_CREDENTIALS"),
        (~active, "REJECTED_INACTIVE"),
        (exiting, "REJECTED_EXITING"),
        (~old, "REJECTED_TOO_YOUNG"),
        (full, choose(pending, "FULL_EXIT_NOOP_PENDING", no="FULL_EXIT_INITIATED")),
        (~compounding, "PARTIAL_NOOP_NOT_COMPOUNDING"),
        (~sufficient, "PARTIAL_NOOP_INSUFFICIENT_EFFECTIVE_BALANCE"),
        (~excess, "PARTIAL_NOOP_NO_EXCESS_BALANCE"),
        "PARTIAL_QUEUED",
    )


outcome = dimension(
    "outcome",
    result(
        full_input,
        queue_input == limit,
        found_input,
        execution,
        compounding,
        address_input,
        active_input,
        exiting_input,
        old_input,
        pending_input,
        effective_input >= minimum,
        balance_input > required_input,
    ),
)
churn = dimension(
    "churn_variant",
    attribute("observed_churn_variant", Finite(("RESET_FIT", "CARRY_FIT", "CARRY_OVERFLOW"))),
    when=outcome == "FULL_EXIT_INITIATED",
)
effect = dimension("withdrawal_effected", boolean("withdrawal_effected"))

AMOUNT = aspect("withdrawal_amount", full)
QUEUE = aspect("partial_queue_capacity", queue)
CHURN = aspect("queue_churn", churn)
VALIDATOR = aspect(
    "validator_state",
    found,
    credential,
    address,
    active,
    exiting,
    old,
    pending,
    effective,
    balance,
)
OUTCOME = aspect("outcome", outcome, effect)
INPUT_ASPECTS = (AMOUNT, QUEUE, CHURN, VALIDATOR)
ASPECTS = (*INPUT_ASPECTS, OUTCOME)
FACTORS = tuple(f for a in ASPECTS for f in a.declarations)

# These gates return without raising. Preserve the legacy independent-fault
# scopes explicitly rather than treating ignored requests as failed assertions.
queue_pass = union(
    fix(is_full_exit_request=True),
    fix(partial_queue_capacity="EMPTY"),
    fix(partial_queue_capacity="AVAILABLE"),
)
queue_fail = fix(is_full_exit_request=False, partial_queue_capacity="FULL")
credential_pass = union(
    *(fix(validator_credential=c, source_address_matches=True) for c in ("ETH1", "COMPOUNDING"))
)
credential_fail = union(
    fix(source_address_matches=False),
    *(fix(validator_credential=c) for c in ("BLS", "BUILDER", "OTHER")),
)
passes = (
    queue_pass,
    credential_pass,
    fix(validator_active=True),
    fix(validator_exiting=False),
    fix(validator_old_enough=True),
)
fails = (
    queue_fail,
    credential_fail,
    fix(validator_active=False),
    fix(validator_exiting=True),
    fix(validator_old_enough=False),
)


def product(plans):
    combined = fix(validator_pubkey_found=True)
    for plan in plans:
        combined = combined * plan
    return combined


NORMAL_SCOPE = product(passes)
SINGLE_FAULT = union(
    queue_pass * fix(validator_pubkey_found=False),
    *(
        product((fails[j] if i == j else plan) for i, plan in enumerate(passes))
        for j in range(len(passes))
    ),
)
# Carry the outcome context when projecting churn: inactive churn still has a
# well-defined branch, and must not drop full-exit-noop or partial requests.
PROJECTIONS = (
    AMOUNT.exhaustive(),
    QUEUE.exhaustive(),
    exhaustive((outcome, churn)),
    VALIDATOR.exhaustive(),
)
NORMAL = union(*(a * b * NORMAL_SCOPE for a, b in combinations(PROJECTIONS, 2)))
EXCEPTIONAL = exhaustive((outcome,)) * SINGLE_FAULT
COVERAGE = coverage_spec(
    "withdrawal_request",
    focus="process_withdrawal_request: validator gates, full exit, partial queue, and churn",
    record="one operation",
    aspects=ASPECTS,
    constraints=(
        implies(found & old & ~exiting, active),
        implies(queue == "EMPTY", ~pending),
        outcome
        == result(
            full,
            queue == "FULL",
            found,
            choose(found, (credential == "ETH1") | (credential == "COMPOUNDING"), no=False),
            choose(found, credential == "COMPOUNDING", no=False),
            address,
            active,
            exiting,
            old,
            pending,
            coverage_value(effective) != "LT",
            coverage_value(balance) == "GT",
        ),
        implies(
            churn == "CARRY_OVERFLOW",
            (coverage_value(effective) == "GT") & (credential == "COMPOUNDING"),
        ),
        effect == ((outcome == "FULL_EXIT_INITIATED") | (outcome == "PARTIAL_QUEUED")),
    ),
    profiles={
        "smoke": OUTCOME.exhaustive(),
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
        "minimum_activation_balance": lambda spec: int(spec.MIN_ACTIVATION_BALANCE),
        "partial_withdrawals_limit": lambda spec: int(spec.PENDING_PARTIAL_WITHDRAWALS_LIMIT),
    },
)
