"""Coverage declaration for Gloas ``process_consolidation_request``."""

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

CREDENTIAL = Finite(("BLS", "ETH1", "COMPOUNDING", "BUILDER", "OTHER"))


def boolean(name):
    return attribute(f"observed_{name}", Boolean())


same_input = boolean("same_source_target")
found_input = boolean("validator_pubkey_found")
credential_input = attribute("observed_validator_credential", CREDENTIAL)
address_input = boolean("source_address_matches")
active_input = boolean("validator_active")
exiting_input = boolean("validator_exiting")
old_input = boolean("validator_old_enough")
pending_input = boolean("has_pending_partial_withdrawal")
target_found_input = boolean("target_found")
target_credential_input = attribute("observed_target_credential", CREDENTIAL)
target_active_input = boolean("target_active")
target_exiting_input = boolean("target_exiting")
queue_input = attribute("observed_queue_length", Integer(min=0))
churn_input = attribute("observed_consolidation_churn", Integer(min=0))
balance_input = attribute("observed_source_balance", Integer(min=0))
minimum = constant("minimum_activation_balance", Integer(min=1))
limit = constant("consolidations_limit", Integer(min=2))

same = dimension("same_source_target", same_input)
queue = dimension(
    "pending_consolidations_capacity",
    choose((queue_input == 0, "EMPTY"), (queue_input == limit, "FULL"), "AVAILABLE"),
)
churn_limit = dimension("consolidation_churn_to_min_activation", cmp3(churn_input, minimum))
found = dimension("validator_pubkey_found", found_input)
credential = dimension("validator_credential", credential_input, when=found)
address = dimension("source_address_matches", address_input, when=found)
active = dimension("validator_active", active_input, when=found)
exiting = dimension("validator_exiting", exiting_input, when=found)
old = dimension("validator_old_enough", old_input, when=found)
pending = dimension("has_pending_partial_withdrawal", pending_input, when=found)
target_found = dimension("target_found", target_found_input, when=~same)
target_credential = dimension(
    "target_credential", target_credential_input, when=(~same) & target_found
)
target_active = dimension("target_active", target_active_input, when=(~same) & target_found)
target_exiting = dimension("target_exiting", target_exiting_input, when=(~same) & target_found)


def result(
    same,
    full,
    sufficient_churn,
    found,
    credential,
    address,
    active,
    exiting,
    old,
    pending,
    target_found,
    target_credential,
    target_active,
    target_exiting,
):
    switch = choose(
        (~found, "SWITCH_REJECTED_SOURCE_NOT_FOUND"),
        (~address, "SWITCH_REJECTED_NOT_AUTHORIZED"),
        (credential != "ETH1", "SWITCH_REJECTED_NOT_ETH1"),
        (~active, "SWITCH_REJECTED_INACTIVE"),
        (exiting, "SWITCH_REJECTED_EXITING"),
        "SWITCHED_TO_COMPOUNDING",
    )
    consolidate = choose(
        (full, "REJECTED_QUEUE_FULL"),
        (~sufficient_churn, "REJECTED_INSUFFICIENT_CHURN"),
        (~found, "REJECTED_SOURCE_NOT_FOUND"),
        (~target_found, "REJECTED_TARGET_NOT_FOUND"),
        (
            ~(((credential == "ETH1") | (credential == "COMPOUNDING")) & address),
            "REJECTED_SOURCE_CREDENTIALS",
        ),
        (target_credential != "COMPOUNDING", "REJECTED_TARGET_NOT_COMPOUNDING"),
        (~active, "REJECTED_SOURCE_INACTIVE"),
        (~target_active, "REJECTED_TARGET_INACTIVE"),
        (exiting, "REJECTED_SOURCE_EXITING"),
        (target_exiting, "REJECTED_TARGET_EXITING"),
        (~old, "REJECTED_SOURCE_TOO_YOUNG"),
        (pending, "REJECTED_SOURCE_PENDING_WITHDRAWAL"),
        "CONSOLIDATED",
    )
    return choose(same, switch, no=consolidate)


outcome = dimension(
    "outcome",
    result(
        same_input,
        queue_input == limit,
        churn_input > minimum,
        found_input,
        credential_input,
        address_input,
        active_input,
        exiting_input,
        old_input,
        pending_input,
        target_found_input,
        target_credential_input,
        target_active_input,
        target_exiting_input,
    ),
)
churn = dimension(
    "churn_variant",
    attribute("observed_churn_variant", Finite(("RESET_FIT", "CARRY_FIT", "CARRY_OVERFLOW"))),
    when=outcome == "CONSOLIDATED",
)
balance = dimension(
    "switch_balance_to_min_activation",
    cmp3(balance_input, minimum),
    when=outcome == "SWITCHED_TO_COMPOUNDING",
)
excess = dimension("switch_excess_queued", boolean("switch_excess_queued"))
effect = dimension("state_effected", boolean("state_effected"))

PAIR = aspect("consolidation_pair", same)
QUEUE = aspect("pending_consolidations_capacity", queue)
CHURN_LIMIT = aspect("consolidation_churn", churn_limit)
CHURN = aspect("churn_state", churn)
SWITCH = aspect("switch_balance", balance, excess)
VALIDATOR = aspect(
    "validator_state",
    found,
    credential,
    address,
    active,
    exiting,
    old,
    pending,
    target_found,
    target_credential,
    target_active,
    target_exiting,
)
OUTCOME = aspect("outcome", outcome, effect)
ASPECTS = (PAIR, QUEUE, CHURN_LIMIT, CHURN, SWITCH, VALIDATOR, OUTCOME)
FACTORS = tuple(f for a in ASPECTS for f in a.declarations)

# Both branches return on a failed gate. These scopes count independently
# applicable gate failures; they do not model rejecting assertions.
SWITCH_GATES = {
    "source_found": (fix(validator_pubkey_found=True), fix(validator_pubkey_found=False)),
    "source_address": (fix(source_address_matches=True), fix(source_address_matches=False)),
    "source_credential": (
        fix(validator_credential="ETH1"),
        union(*(fix(validator_credential=c) for c in ("BLS", "COMPOUNDING", "BUILDER", "OTHER"))),
    ),
    "source_active": (fix(validator_active=True), fix(validator_active=False)),
    "source_exit": (fix(validator_exiting=False), fix(validator_exiting=True)),
}
CONSOLIDATION_GATES = {
    "queue": (
        union(
            fix(pending_consolidations_capacity="EMPTY"),
            fix(pending_consolidations_capacity="AVAILABLE"),
        ),
        fix(pending_consolidations_capacity="FULL"),
    ),
    "churn": (
        fix(consolidation_churn_to_min_activation="GT"),
        union(
            fix(consolidation_churn_to_min_activation="LT"),
            fix(consolidation_churn_to_min_activation="EQ"),
        ),
    ),
    "source_found": SWITCH_GATES["source_found"],
    "target_found": (fix(target_found=True), fix(target_found=False)),
    "source_credential": (
        union(
            *(
                fix(validator_credential=c, source_address_matches=True)
                for c in ("ETH1", "COMPOUNDING")
            )
        ),
        union(
            fix(source_address_matches=False),
            *(fix(validator_credential=c) for c in ("BLS", "BUILDER", "OTHER")),
        ),
    ),
    "source_active": SWITCH_GATES["source_active"],
    "source_exit": SWITCH_GATES["source_exit"],
    "source_age": (fix(validator_old_enough=True), fix(validator_old_enough=False)),
    "source_pending": (
        fix(has_pending_partial_withdrawal=False),
        fix(has_pending_partial_withdrawal=True),
    ),
    "target_active": (fix(target_active=True), fix(target_active=False)),
    "target_exit": (fix(target_exiting=False), fix(target_exiting=True)),
    "target_credential": (
        fix(target_credential="COMPOUNDING"),
        union(*(fix(target_credential=c) for c in ("BLS", "ETH1", "BUILDER", "OTHER"))),
    ),
}


def product(plans, *, same):
    combined = fix(same_source_target=same)
    for plan in plans:
        combined = combined * plan
    return combined


def single_fault(gates, failed, *, same):
    # An unresolved role deactivates its remaining predicates, so those gates
    # must not be required to pass when membership is the sole failure.
    bypassed_prefix = failed.removesuffix("found") if failed.endswith("_found") else None
    return product(
        (
            bad if name == failed else good
            for name, (good, bad) in gates.items()
            if name == failed or bypassed_prefix is None or not name.startswith(bypassed_prefix)
        ),
        same=same,
    )


NORMAL_SCOPE = union(
    product((good for good, _ in SWITCH_GATES.values()), same=True),
    product((good for good, _ in CONSOLIDATION_GATES.values()), same=False),
)
SINGLE_FAULT = union(
    *(single_fault(SWITCH_GATES, name, same=True) for name in SWITCH_GATES),
    *(single_fault(CONSOLIDATION_GATES, name, same=False) for name in CONSOLIDATION_GATES),
)
PROJECTIONS = (
    PAIR.exhaustive(),
    QUEUE.exhaustive(),
    CHURN_LIMIT.exhaustive(),
    exhaustive((outcome, churn)),
    exhaustive((outcome, balance, excess)),
    VALIDATOR.exhaustive(),
)
NORMAL = union(*(a * b * NORMAL_SCOPE for a, b in combinations(PROJECTIONS, 2)))
EXCEPTIONAL = OUTCOME.exhaustive() * SINGLE_FAULT
COVERAGE = coverage_spec(
    "consolidation_request",
    focus="process_consolidation_request: switch, validator roles, queues, and churn",
    record="one operation",
    aspects=ASPECTS,
    constraints=(
        implies(found & old & ~exiting, active),
        outcome
        == result(
            same,
            queue == "FULL",
            coverage_value(churn_limit) == "GT",
            found,
            credential,
            address,
            active,
            exiting,
            old,
            pending,
            target_found,
            target_credential,
            target_active,
            target_exiting,
        ),
        implies(churn == "CARRY_OVERFLOW", credential == "COMPOUNDING"),
        excess
        == choose(outcome == "SWITCHED_TO_COMPOUNDING", coverage_value(balance) == "GT", no=False),
        effect == ((outcome == "SWITCHED_TO_COMPOUNDING") | (outcome == "CONSOLIDATED")),
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
        "consolidations_limit": lambda spec: int(spec.PENDING_CONSOLIDATIONS_LIMIT),
    },
)
