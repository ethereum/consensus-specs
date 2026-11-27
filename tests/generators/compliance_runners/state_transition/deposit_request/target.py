"""Coverage declaration for Gloas ``process_deposit_request``."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    coverage_spec,
    dimension,
    each,
    exhaustive,
    Finite,
    union,
)

from .observation import observe_attributes

amount_profile_input = attribute(
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
withdrawal_credentials_input = attribute(
    "observed_withdrawal_credentials_profile",
    Finite(("BLS", "ETH1", "COMPOUNDING", "BUILDER", "OTHER")),
)
signature_valid_input = attribute("observed_signature_valid", Boolean())
pubkey_is_existing_validator_input = attribute("observed_pubkey_is_existing_validator", Boolean())

AMOUNT = aspect("deposit_amount", dimension("amount_profile", amount_profile_input))
CREDENTIALS = aspect(
    "withdrawal_credentials",
    dimension("withdrawal_credentials_profile", withdrawal_credentials_input),
)
SIGNATURE = aspect(
    "signature",
    dimension("signature_profile", choose(signature_valid_input, "VALID", "INVALID")),
)
PUBKEY = aspect(
    "deposit_pubkey",
    dimension("pubkey_is_existing_validator", pubkey_is_existing_validator_input),
)
ASPECTS = (AMOUNT, CREDENTIALS, SIGNATURE, PUBKEY)
FACTORS = tuple(f for aspect_ in ASPECTS for f in aspect_.declarations)
NORMAL = union(
    *(left.exhaustive() * right.exhaustive() for left, right in combinations(ASPECTS, 2))
)

COVERAGE = coverage_spec(
    "deposit_request",
    focus="process_deposit_request: amount, withdrawal credentials, signature, and pubkey shape",
    record="one operation",
    aspects=ASPECTS,
    profiles={
        "smoke": each(FACTORS),
        "normal": NORMAL,
        "max": exhaustive(FACTORS),
        "standard": NORMAL,
    },
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes, backend="python")
