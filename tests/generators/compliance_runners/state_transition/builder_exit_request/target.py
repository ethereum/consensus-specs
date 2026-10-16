"""Coverage declaration for Gloas ``process_builder_exit_request``."""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    cmp3,
    coverage_spec,
    dimension,
    exhaustive,
    fix,
    implies,
    Integer,
    union,
)

from .observation import observe_attributes

found_input = attribute("observed_builder_pubkey_found", Boolean())
deposit_input = attribute("observed_builder_deposit_epoch", Integer(min=0))
finalized_input = attribute("observed_finalized_epoch", Integer(min=0))
withdrawable_input = attribute("observed_builder_withdrawable_epoch_set", Boolean())
withdrawal_input = attribute("observed_builder_has_pending_withdrawal", Boolean())
payment_input = attribute("observed_builder_has_pending_payment", Boolean())
address_input = attribute("observed_source_address_matches", Boolean())
active_input = attribute("observed_builder_active", Boolean())
pending_input = attribute("observed_builder_has_pending_balance", Boolean())
exit_input = attribute("observed_exit_initiated", Boolean())

found = dimension("builder_pubkey_found", found_input)
deposit = dimension(
    "builder_deposit_to_finalized_epoch",
    cmp3(deposit_input, finalized_input, op="<"),
    when=found,
)
withdrawable = dimension("builder_withdrawable_epoch_set", withdrawable_input, when=found)
withdrawal = dimension("builder_has_pending_withdrawal", withdrawal_input, when=found)
payment = dimension("builder_has_pending_payment", payment_input, when=found)
address = dimension("source_address_matches", address_input, when=found)
active = dimension("builder_active", active_input)
pending = dimension("builder_has_pending_balance", pending_input)
outcome = dimension(
    "outcome",
    choose(
        (~found_input, "IGNORED_PUBKEY_NOT_FOUND"),
        (~active_input, "IGNORED_NOT_ACTIVE"),
        (~address_input, "IGNORED_ADDRESS_MISMATCH"),
        (pending_input, "IGNORED_PENDING_NONZERO"),
        "EXIT_INITIATED",
    ),
)
exit_initiated = dimension("exit_initiated", exit_input)

MEMBERSHIP = aspect("builder_membership", found)
LIFECYCLE = aspect("builder_lifecycle", deposit, withdrawable, active)
PENDING = aspect("builder_pending_balance", withdrawal, payment, pending)
AUTHORIZATION = aspect("source_authorization", address)
OUTCOME = aspect("outcome", outcome, exit_initiated)
ASPECTS = (MEMBERSHIP, LIFECYCLE, PENDING, AUTHORIZATION, OUTCOME)
FACTORS = tuple(f for a in ASPECTS for f in a.declarations)

# These are ignored-operation branches, not rejecting assertions. The one-fault
# profile preserves the former independently applicable gate-failure policy.
SINGLE_FAULT = union(
    fix(builder_pubkey_found=False),
    fix(builder_pubkey_found=True, builder_active=False, source_address_matches=True),
    fix(builder_active=True, source_address_matches=False, builder_has_pending_balance=False),
    fix(builder_active=True, source_address_matches=True, builder_has_pending_balance=True),
)
NORMAL = fix(outcome="EXIT_INITIATED")
EXCEPTIONAL = exhaustive((outcome,)) * SINGLE_FAULT
COVERAGE = coverage_spec(
    "builder_exit_request",
    focus="process_builder_exit_request: membership, lifecycle, authorization, and pending balance",
    record="one operation",
    aspects=ASPECTS,
    constraints=(
        active == choose(found, deposit & ~withdrawable, no=False),
        pending == choose(found, withdrawal | payment, no=False),
        # Retain the legacy materializer's scope: pending funds belong to an
        # active builder. This is a fixture constraint, not a protocol rule.
        implies(pending, active),
        outcome
        == choose(
            (~found, "IGNORED_PUBKEY_NOT_FOUND"),
            (~active, "IGNORED_NOT_ACTIVE"),
            (~address, "IGNORED_ADDRESS_MISMATCH"),
            (pending, "IGNORED_PENDING_NONZERO"),
            "EXIT_INITIATED",
        ),
        exit_initiated == (outcome == "EXIT_INITIATED"),
    ),
    profiles={
        "smoke": exhaustive((outcome,)),
        "normal": NORMAL,
        "exceptional": EXCEPTIONAL,
        "standard": union(NORMAL, EXCEPTIONAL),
        "max": exhaustive(FACTORS),
    },
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes, backend="python")
