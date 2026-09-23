"""Coverage declarations for Gloas process_voluntary_exit and its exit-churn slice."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import rules
from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    categorical,
    choose,
    comparison,
    constant,
    coverage_spec,
    derived,
    each,
    factor,
    fix,
    Integer,
    nwise,
    union,
)

from .observation import observe_attributes

validator_index = attribute("validator_index", Integer(min=0))
validator_found = attribute("validator_found", Boolean())
current_epoch = attribute("current_epoch", Integer(min=0))
message_epoch = attribute("message_epoch", Integer(min=0))
activation_epoch = attribute("activation_epoch", Integer(min=0))
exit_epoch = attribute("exit_epoch", Integer(min=0))
matching_pending = attribute("matching_pending", Integer(min=0))
foreign_pending = attribute("foreign_pending", Integer(min=0))
pending_balance = attribute("pending_balance", Integer(min=0))
signature_valid = attribute("signature_valid", Boolean())
earliest_exit_epoch = attribute("earliest_exit_epoch", Integer(min=0))
new_exit_epoch = attribute("new_exit_epoch", Integer(min=0))
exit_balance_to_consume = attribute("exit_balance_to_consume", Integer(min=0))
per_epoch_churn = attribute("per_epoch_churn", Integer(min=1))
effective_balance = attribute("effective_balance", Integer(min=0))
post_present = attribute("post_present", Boolean())

far_future_epoch = constant("far_future_epoch", Integer(min=0))
shard_committee_period = constant("shard_committee_period", Integer(min=0))
COUNTS = ("ZERO", "ONE", "MANY")

EPOCHS = aspect(
    "epochs",
    comparison(
        "activation_le_current",
        activation_epoch,
        current_epoch,
        op="<=",
        available_when=validator_found,
    ),
    comparison(
        "current_lt_exit", current_epoch, exit_epoch, op="<", available_when=validator_found
    ),
    factor("exit_not_initiated", exit_epoch == far_future_epoch, available_when=validator_found),
    comparison(
        "current_ge_message_epoch",
        current_epoch,
        message_epoch,
        op=">=",
        available_when=validator_found,
    ),
    comparison(
        "current_ge_seasoned",
        current_epoch,
        activation_epoch + shard_committee_period,
        op=">=",
        available_when=validator_found,
    ),
)
PENDING = aspect(
    "pending",
    factor("pending_balance_zero", pending_balance == 0),
    categorical(
        "matching_pending_entries",
        choose(matching_pending == 0, "ZERO", choose(matching_pending == 1, "ONE", "MANY")),
        COUNTS,
    ),
    categorical(
        "foreign_pending_entries", choose(foreign_pending == 0, "ZERO", "SOME"), ("ZERO", "SOME")
    ),
)
SIGNATURE = aspect(
    "signature", factor("signature_ok", signature_valid, available_when=validator_found)
)
consumable = derived(
    "consumable",
    choose(earliest_exit_epoch < new_exit_epoch, per_epoch_churn, exit_balance_to_consume),
)
EXCEEDS = comparison(
    "balance_gt_consumable", effective_balance, consumable, op=">", available_when=validator_found
)
CHURN = aspect(
    "churn",
    comparison("earliest_lt_new", earliest_exit_epoch, new_exit_epoch, op="<"),
    EXCEEDS,
    # For a positive excess, ceil(excess / churn) is one iff excess <= churn.
    categorical(
        "additional_epochs",
        choose(effective_balance - consumable <= per_epoch_churn, "ONE", "MANY"),
        ("ONE", "MANY"),
        when=EXCEEDS,
    ),
)
OUTCOME = aspect("outcome", factor("accepted", post_present))
ACCEPTED = OUTCOME["accepted"]
ASPECTS = (EPOCHS, PENDING, SIGNATURE, CHURN, OUTCOME)
# The handler's assertion chain: accepted <=> all of these hold.
GATES = (
    EPOCHS["activation_le_current"],
    EPOCHS["current_lt_exit"],
    EPOCHS["exit_not_initiated"],
    EPOCHS["current_ge_message_epoch"],
    EPOCHS["current_ge_seasoned"],
    PENDING["pending_balance_zero"],
    SIGNATURE["signature_ok"],
)


def _holds(a: dict, f, g) -> bool | None:
    return None if f.name not in a else f.holds(a[f.name], g)


def _far_below(a: dict, f, g: str) -> bool:
    """``lhs < rhs`` by more than one, as far as the granularity can tell."""
    return bool(_holds(a, f, g)) and f.far(a[f.name], g) is not False


def _uninitiated_exit_is_far(a: dict, g: str) -> bool:
    if _holds(a, EPOCHS["exit_not_initiated"], g) is True and "current_lt_exit" in a:
        return _far_below(a, EPOCHS["current_lt_exit"], g)
    return True


def _seasoned_is_activated_long_ago(a: dict, g: str) -> bool:
    if _holds(a, EPOCHS["current_ge_seasoned"], g) is True and "activation_le_current" in a:
        return _far_below(a, EPOCHS["activation_le_current"], g)
    return True


def _accepted_iff_all_gates(a: dict, g: str) -> bool:
    accepted = _holds(a, ACCEPTED, g)
    if accepted is None:
        return True
    gates = [_holds(a, f, g) for f in GATES]
    if accepted:
        return all(h is not False for h in gates)
    # Rejected, yet every gate is assigned and holds: impossible.
    return not all(h is True for h in gates)


def _pending_balance_needs_entries(a: dict, g: str) -> bool:
    if _holds(a, PENDING["pending_balance_zero"], g) is False:
        return a.get("matching_pending_entries") != "ZERO"
    return True


FEASIBLE = rules(
    _uninitiated_exit_is_far,
    _seasoned_is_activated_long_ago,
    _accepted_iff_all_gates,
    _pending_balance_needs_entries,
)

NORMAL = fix(accepted=True)
EXCEPTIONAL = fix(accepted=False)
ALL_FACTORS = [f for a in ASPECTS for f in a.declarations]
CHURN_ARITHMETIC = CHURN.exhaustive()
PROFILES = {
    "smoke": each(ALL_FACTORS),
    "normal": NORMAL * (CHURN_ARITHMETIC | EPOCHS.nwise(2)),
    "exceptional": EXCEPTIONAL * nwise(ALL_FACTORS, 2),
    "standard": union(
        each(ALL_FACTORS), *(a.each() * b.each() for a, b in combinations(ASPECTS, 2))
    ),
    "pending_loop": PENDING.exhaustive() * OUTCOME.each(),
}
COVERAGE = coverage_spec(
    "voluntary_exit",
    focus="voluntary-exit assertions, pending-withdrawal shape, and exit-churn arithmetic",
    record="one vector",
    attributes=(
        validator_index,
        validator_found,
        current_epoch,
        message_epoch,
        activation_epoch,
        exit_epoch,
        matching_pending,
        foreign_pending,
        pending_balance,
        signature_valid,
        earliest_exit_epoch,
        new_exit_epoch,
        exit_balance_to_consume,
        per_epoch_churn,
        effective_balance,
        post_present,
    ),
    constants=(far_future_epoch, shard_committee_period),
    aspects=ASPECTS,
    profiles=PROFILES,
    feasible=FEASIBLE,
)
TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "far_future_epoch": lambda spec: int(spec.FAR_FUTURE_EPOCH),
        "shard_committee_period": lambda spec: int(spec.config.SHARD_COMMITTEE_PERIOD),
    },
)
