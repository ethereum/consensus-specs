"""Assertion and branch coverage for Gloas ``process_proposer_slashing``."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    aspect,
    assertion,
    assertion_set,
    attribute,
    bind,
    Boolean,
    constant,
    coverage_spec,
    dimension,
    each,
    exhaustive,
    Finite,
    implies,
    Integer,
    nwise,
    union,
)

from .observation import observe_attributes

slot_1 = attribute("slot_1", Integer(min=0))
slot_2 = attribute("slot_2", Integer(min=0))
proposer_1 = attribute("proposer_1", Integer(min=0))
proposer_2 = attribute("proposer_2", Integer(min=0))
headers_equal = attribute("headers_equal", Boolean())
proposer_found = attribute("proposer_found", Boolean())
slashed = attribute("slashed", Boolean())
activation_epoch = attribute("activation_epoch", Integer(min=0))
withdrawable_epoch = attribute("withdrawable_epoch", Integer(min=0))
exit_epoch = attribute("exit_epoch", Integer(min=0))
current_epoch = attribute("current_epoch", Integer(min=0))
valid_signature_1 = attribute("valid_signature_1", Boolean())
valid_signature_2 = attribute("valid_signature_2", Boolean())
window = attribute("window", Finite(("CURRENT", "PREVIOUS", "OLD")))
payment_matches = attribute("payment_matches", Boolean())
payment_present = attribute("payment_present", Boolean())
churn = attribute("churn", Finite(("RESET_FIT", "CARRY_FIT", "CARRY_OVERFLOW")))
post_present = attribute("post_present", Boolean())
payment_empty_after = attribute("payment_empty_after", Boolean())
far_future_epoch = constant("far_future_epoch", Integer(min=0))

HEADERS = aspect(
    "headers",
    assertion("slots_match", slot_1 == slot_2),
    assertion("proposers_match", proposer_1 == proposer_2),
    assertion("headers_different", ~headers_equal),
)
SLASHABILITY = aspect(
    "slashability",
    assertion("proposer_not_slashed", ~slashed, available_when=proposer_found),
    assertion(
        "proposer_activated", activation_epoch <= current_epoch, available_when=proposer_found
    ),
    assertion(
        "proposer_not_withdrawable",
        current_epoch < withdrawable_epoch,
        available_when=proposer_found,
    ),
    # An initiated exit does not prevent slashing until withdrawability.
    dimension("exit_initiated", exit_epoch != far_future_epoch, available_when=proposer_found),
)
SIGNATURES = aspect(
    "signatures",
    assertion("signature_1_valid", valid_signature_1, available_when=proposer_found),
    assertion("signature_2_valid", valid_signature_2, available_when=proposer_found),
)
PAYMENT_WINDOW = dimension("payment_window", window)
PAYMENTS = aspect(
    "payments",
    PAYMENT_WINDOW,
    dimension("payment_proposer_matches", payment_matches, when=PAYMENT_WINDOW != "OLD"),
)
ACCEPTED = dimension("accepted", post_present)
CHURN = aspect(
    "churn",
    dimension("churn_variant", churn, when=ACCEPTED & ~SLASHABILITY.ref("exit_initiated")),
)
RESULT = aspect(
    "result",
    ACCEPTED,
    dimension(
        "pending_payment_cleared",
        payment_empty_after,
        when=ACCEPTED & (PAYMENT_WINDOW != "OLD"),
        available_when=payment_present,
    ),
)
ASPECTS = (HEADERS, SLASHABILITY, SIGNATURES, PAYMENTS, CHURN, RESULT)
ASSERTIONS = assertion_set(HEADERS, SLASHABILITY, SIGNATURES, observed=ACCEPTED, complete=True)
FACTORS = tuple(f for a in ASPECTS for f in a.declarations)
NORMAL = ASSERTIONS.normal(
    union(*(a.exhaustive() * b.exhaustive() for a, b in combinations(ASPECTS, 2)))
)
EXCEPTIONAL = ASSERTIONS.exceptional(each(FACTORS), faults=1)
PROFILES = {
    "smoke": each(FACTORS) | ASSERTIONS.normal(PAYMENTS.exhaustive()),
    "normal": NORMAL,
    "exceptional": EXCEPTIONAL,
    "standard": NORMAL | EXCEPTIONAL,
    # Preserve the provider policy: exhaustive through two faults, pairwise above.
    "max": union(
        ASSERTIONS.normal(exhaustive(FACTORS)),
        ASSERTIONS.exceptional(exhaustive(FACTORS), faults=(1, 2)),
        ASSERTIONS.exceptional(nwise(FACTORS, 2)),
    ),
}
COVERAGE = coverage_spec(
    "proposer_slashing",
    focus="header and signature assertions, slashability, pending payments, and exit churn",
    record="one vector",
    aspects=ASPECTS,
    profiles=PROFILES,
    assertions=ASSERTIONS,
    constraints=(
        implies(
            ~HEADERS.ref("headers_different"),
            all_of(HEADERS.ref("slots_match"), HEADERS.ref("proposers_match")),
        ),
        implies(
            ACCEPTED & (PAYMENT_WINDOW != "OLD"),
            RESULT.ref("pending_payment_cleared") == PAYMENTS.ref("payment_proposer_matches"),
        ),
    ),
)
TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={"far_future_epoch": lambda spec: int(spec.FAR_FUTURE_EPOCH)},
)
