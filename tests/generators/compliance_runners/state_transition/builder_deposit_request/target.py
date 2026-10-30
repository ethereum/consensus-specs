"""Coverage declaration for Gloas ``process_builder_deposit_request``."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    coverage_spec,
    dimension,
    exhaustive,
    Finite,
    fix,
    union,
)

from .observation import observe_attributes

credentials_input = attribute(
    "observed_withdrawal_credentials_profile",
    Finite(("BLS", "ETH1", "COMPOUNDING", "BUILDER", "OTHER")),
)
found_input = attribute("observed_builder_pubkey_found", Boolean())
signature_input = attribute("observed_builder_signature_valid", Boolean())
amount_input = attribute(
    "observed_amount_profile",
    Finite(
        (
            "ZERO",
            "BELOW_MINIMUM",
            "MINIMUM",
            "BETWEEN_MINIMUM_AND_ACTIVATION",
            "ACTIVATION",
            "ABOVE_ACTIVATION",
        )
    ),
)
withdrawable_input = attribute("observed_builder_withdrawable_epoch_set", Boolean())
zero_input = attribute("observed_builder_balance_zero", Boolean())
reuse_input = attribute("observed_reuses_swept_slot", Boolean())

credentials = dimension("withdrawal_credentials_profile", credentials_input)
prefix = dimension("wc_is_builder_prefix", credentials_input == "BUILDER")
found = dimension("builder_pubkey_found", found_input)
signature = dimension("builder_signature_valid", signature_input)
amount = dimension("amount_profile", amount_input)
withdrawable = dimension("builder_withdrawable_epoch_set", withdrawable_input, when=found)
zero = dimension("builder_balance_zero", zero_input, when=found)
reset = dimension(
    "reset_applies",
    choose(found_input, withdrawable_input & zero_input, no=False),
)
outcome = dimension(
    "outcome",
    choose(
        (credentials_input != "BUILDER", "IGNORED_BAD_PREFIX"),
        (
            ~found_input,
            choose(signature_input, "ADDED_NEW_BUILDER", no="IGNORED_BAD_SIGNATURE"),
        ),
        (reset.value, "TOPPED_UP_AFTER_RESET"),
        "TOPPED_UP",
    ),
)
reuse = dimension("reuses_swept_slot", reuse_input, when=outcome == "ADDED_NEW_BUILDER")
credited = dimension(
    "builder_credited",
    (outcome.value == "ADDED_NEW_BUILDER")
    | (outcome.value == "TOPPED_UP")
    | (outcome.value == "TOPPED_UP_AFTER_RESET"),
)

CREDENTIALS = aspect("withdrawal_credential", credentials, prefix)
MEMBERSHIP = aspect("builder_membership", found)
SIGNATURE = aspect("signed_message", signature)
AMOUNT = aspect("deposit_amount", amount)
RESET = aspect("builder_reset", withdrawable, zero, reset)
REGISTRY = aspect("builder_registry", reuse)
OUTCOME = aspect("outcome", outcome, credited)
# Carry the branch context even when its conditional dimensions are absent.
# This distinguishes an inapplicable reset/reuse case from an active one.
INPUT_PROJECTIONS = (
    exhaustive((credentials,)),
    exhaustive((found,)),
    exhaustive((signature,)),
    exhaustive((amount,)),
    exhaustive((found, withdrawable, zero)),
    exhaustive((outcome, reuse)),
)
ASPECTS = (CREDENTIALS, MEMBERSHIP, SIGNATURE, AMOUNT, RESET, REGISTRY, OUTCOME)
FACTORS = tuple(f for a in ASPECTS for f in a.declarations)

# Ignored requests are exceptional branches, not assertion failures: the
# handler always supplies a post-state. Signature validity remains observable
# even when the prefix or existing-builder path bypasses verification.
NORMAL_OUTCOMES = union(
    *(fix(outcome=value) for value in ("ADDED_NEW_BUILDER", "TOPPED_UP", "TOPPED_UP_AFTER_RESET"))
)
NORMAL = union(
    *(left * right * NORMAL_OUTCOMES for left, right in combinations(INPUT_PROJECTIONS, 2))
)
EXCEPTIONAL = union(fix(outcome="IGNORED_BAD_PREFIX"), fix(outcome="IGNORED_BAD_SIGNATURE"))
COVERAGE = coverage_spec(
    "builder_deposit_request",
    focus="process_builder_deposit_request: prefix, membership, signature, reset, and slot reuse",
    record="one operation",
    aspects=ASPECTS,
    constraints=(
        prefix == (credentials == "BUILDER"),
        reset == choose(found, withdrawable & zero, no=False),
        outcome
        == choose(
            (~prefix, "IGNORED_BAD_PREFIX"),
            (~found, choose(signature, "ADDED_NEW_BUILDER", no="IGNORED_BAD_SIGNATURE")),
            (reset, "TOPPED_UP_AFTER_RESET"),
            "TOPPED_UP",
        ),
        credited
        == (
            (outcome == "ADDED_NEW_BUILDER")
            | (outcome == "TOPPED_UP")
            | (outcome == "TOPPED_UP_AFTER_RESET")
        ),
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
