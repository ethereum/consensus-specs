"""Coverage declaration for the single pending-builder-withdrawal provider."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    aspect,
    attribute,
    bind,
    Boolean,
    cmp3,
    constant,
    coverage_spec,
    coverage_value,
    dimension,
    exhaustive,
    Integer,
    union,
)

from .observation import observe_attributes

parent_input = attribute("observed_parent_hash_matches", Boolean())
amount_input = attribute("observed_pending_amount", Integer(min=1))
balance_input = attribute("observed_builder_balance", Integer(min=1))
version_input = attribute("observed_version_valid", Boolean())
current_input = attribute("observed_current_epoch", Integer(min=0))
deposit_input = attribute("observed_deposit_epoch", Integer(min=0))
withdrawable_input = attribute("observed_withdrawable_epoch", Integer(min=0))
finalized_input = attribute("observed_finalized_epoch", Integer(min=0))
exiting_input = attribute("observed_withdrawable_epoch_set", Boolean())
payments_input = attribute("observed_has_pending_payments", Boolean())
withdrawals_input = attribute("observed_has_pending_withdrawals", Boolean())
balance_applied_input = attribute("observed_balance_applied", Boolean())
consumed_input = attribute("observed_queue_consumed", Boolean())
minimum = constant("minimum_deposit", Integer(min=1))

parent = dimension("state_latest_block_hash_match", parent_input)
amount = dimension("cmp_pending_amount_zero", cmp3(amount_input, 0))
balance_amount = dimension("cmp_builder_balance_amount", cmp3(balance_input, amount_input))
version = dimension("payload_builder_version", version_input)
current_deposit = dimension(
    "cmp_state_epoch_deposit_epoch", cmp3(current_input, deposit_input, op=">=")
)
current_withdrawable = dimension(
    "cmp_state_epoch_withdrawal_epoch", cmp3(current_input, withdrawable_input)
)
finalized_deposit = dimension(
    "cmp_finalized_epoch_deposit_epoch", cmp3(finalized_input, deposit_input)
)
exiting = dimension("withdrawable_epoch_set", exiting_input)
balance_zero = dimension("cmp_balance_zero", cmp3(balance_input, 0))
balance_minimum = dimension("cmp_balance_min_deposit", cmp3(balance_input, minimum))
payments = dimension("has_pending_payments", payments_input)
withdrawals = dimension("has_pending_withdrawals", withdrawals_input)
balance_applied = dimension("withdrawal_balance_applied", balance_applied_input)
consumed = dimension("pending_withdrawal_consumed", consumed_input)

PAYLOAD = aspect("payload", parent)
AMOUNT = aspect("amount", amount, balance_amount)
BUILDER = aspect(
    "builder",
    version,
    current_deposit,
    current_withdrawable,
    finalized_deposit,
    exiting,
    balance_zero,
    balance_minimum,
    payments,
    withdrawals,
)
EFFECTS = aspect("effects", balance_applied, consumed)
ASPECTS = (PAYLOAD, AMOUNT, BUILDER, EFFECTS)
FACTORS = tuple(f for a in ASPECTS for f in a.declarations)
NORMAL = union(*(a.exhaustive() * b.exhaustive() for a, b in combinations(ASPECTS, 2)))
SMOKE = union(*(a.exhaustive() for a in ASPECTS))
COVERAGE = coverage_spec(
    "builder_pending_withdrawal_processing",
    focus="process_withdrawals: positive pending builder withdrawal, balance boundary, and queue consumption",
    record="one withdrawals-processing step",
    aspects=ASPECTS,
    constraints=(
        # The legacy slice always resolves a valid active builder with a
        # positive pending withdrawal and balance above the minimum deposit.
        all_of(
            parent,
            version,
            current_deposit,
            finalized_deposit,
            ~exiting,
            withdrawals,
            balance_applied,
            consumed,
        ),
        coverage_value(current_withdrawable) == "LT",
        coverage_value(balance_minimum) == "GT",
    ),
    profiles={
        "smoke": SMOKE,
        "normal": NORMAL,
        "standard": NORMAL,
        "exceptional": SMOKE,
        "max": exhaustive(FACTORS),
    },
)

TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={"minimum_deposit": lambda spec: int(spec.MIN_DEPOSIT_AMOUNT)},
    backend="python",
)
