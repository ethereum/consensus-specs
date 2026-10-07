"""Coverage declarations for Gloas process_voluntary_exit and its exit-churn slice."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    aspect,
    attribute,
    bind,
    Boolean,
    categorical,
    choose,
    comparison,
    constant,
    coverage_spec,
    coverage_value,
    derived,
    each,
    factor,
    fix,
    implies,
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
balance_increment = constant("balance_increment", Integer(min=1))
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
        granularity="cmp5",
        available_when=validator_found,
    ),
    comparison(
        "current_ge_seasoned",
        current_epoch,
        activation_epoch + shard_committee_period,
        op=">=",
        granularity="cmp5",
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
    "balance_gt_consumable",
    effective_balance,
    consumable,
    op=">",
    granularity="cmp5",
    available_when=validator_found,
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
ASPECTS = (EPOCHS, PENDING, SIGNATURE, CHURN, OUTCOME)
# The handler's assertion chain: accepted <=> all of these hold.
GATES = (
    EPOCHS.ref("activation_le_current"),
    EPOCHS.ref("current_lt_exit"),
    EPOCHS.ref("exit_not_initiated"),
    EPOCHS.ref("current_ge_message_epoch"),
    EPOCHS.ref("current_ge_seasoned"),
    PENDING.ref("pending_balance_zero"),
    SIGNATURE.ref("signature_ok"),
)


CONSTRAINTS = (
    implies(EPOCHS.ref("exit_not_initiated"), EPOCHS.ref("current_lt_exit")),
    implies(EPOCHS.ref("current_ge_seasoned"), EPOCHS.ref("activation_le_current")),
    OUTCOME.ref("accepted") == all_of(*GATES),
    implies(
        ~PENDING.ref("pending_balance_zero"), PENDING.ref("matching_pending_entries") != "ZERO"
    ),
    # Fresh churn is aligned; carried budgets can reflect partial withdrawals.
    implies(
        (balance_increment > 1) & CHURN.ref("earliest_lt_new"),
        (coverage_value(EXCEEDS) != "LT_1") & (coverage_value(EXCEEDS) != "GT_1"),
    ),
    # A one-Gwei excess fits in one epoch for any positive churn limit.
    implies(coverage_value(EXCEEDS) == "GT_1", CHURN.ref("additional_epochs") != "MANY"),
)

NORMAL = fix(accepted=True)
EXCEPTIONAL = fix(accepted=False)
ALL_FACTORS = [f for a in ASPECTS for f in a.declarations]
CHURN_ARITHMETIC = CHURN.exhaustive()
PROFILES = {
    "smoke": each(ALL_FACTORS),
    "normal": NORMAL * (CHURN_ARITHMETIC | EPOCHS.nwise(2)),
    "exceptional": EXCEPTIONAL * nwise(ALL_FACTORS, 2),
    "max": union(
        NORMAL
        * union(EPOCHS.exhaustive(), PENDING.exhaustive(), CHURN_ARITHMETIC, nwise(ALL_FACTORS, 3)),
        EXCEPTIONAL * nwise(ALL_FACTORS, 2),
    ),
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
    constants=(far_future_epoch, shard_committee_period, balance_increment),
    aspects=ASPECTS,
    profiles=PROFILES,
    constraints=CONSTRAINTS,
)
TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "far_future_epoch": lambda spec: int(spec.FAR_FUTURE_EPOCH),
        "shard_committee_period": lambda spec: int(spec.config.SHARD_COMMITTEE_PERIOD),
        "balance_increment": lambda spec: int(spec.EFFECTIVE_BALANCE_INCREMENT),
    },
)
