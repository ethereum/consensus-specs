"""Coverage declaration for Gloas ``process_bls_to_execution_change``."""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    any_of,
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    coverage_spec,
    dimension,
    exhaustive,
    fix,
    union,
)

from .observation import observe_attributes

index_input = attribute("observed_validator_index_in_range", Boolean())
credential_input = attribute("observed_has_bls_withdrawal_credential", Boolean())
pubkey_input = attribute("observed_from_pubkey_matches", Boolean())
signature_input = attribute("observed_signature_valid", Boolean())

VALIDATOR = aspect("validator", dimension("validator_index_in_range", index_input))
CREDENTIAL = aspect(
    "credential",
    dimension("has_bls_withdrawal_credential", credential_input),
    dimension("from_pubkey_matches", pubkey_input),
)
SIGNATURE = aspect("signature", dimension("signature_valid", signature_input))
OUTCOME = aspect(
    "outcome",
    dimension(
        "outcome",
        choose(
            (~index_input, "REJECT_INDEX"),
            (~credential_input, "REJECT_CREDENTIAL_PREFIX"),
            (~pubkey_input, "REJECT_PUBKEY_MISMATCH"),
            (~signature_input, "REJECT_SIGNATURE"),
            "ACCEPT",
        ),
    ),
)
ASPECTS = (VALIDATOR, CREDENTIAL, SIGNATURE, OUTCOME)
FACTORS = tuple(f for aspect_ in ASPECTS for f in aspect_.declarations)

VALID_SCENARIOS = (
    (True, True, True, True, "ACCEPT"),
    (True, True, True, False, "REJECT_SIGNATURE"),
    (True, True, False, True, "REJECT_PUBKEY_MISMATCH"),
    (True, False, False, True, "REJECT_CREDENTIAL_PREFIX"),
    (False, False, False, True, "REJECT_INDEX"),
)
SCENARIO_CONSTRAINTS = (
    any_of(
        *(
            all_of(*(factor == value for factor, value in zip(FACTORS, values, strict=True)))
            for values in VALID_SCENARIOS
        )
    ),
)

NORMAL = fix(
    validator_index_in_range=True,
    has_bls_withdrawal_credential=True,
    from_pubkey_matches=True,
    signature_valid=True,
    outcome="ACCEPT",
)
EXCEPTIONAL_OUTCOMES = (
    "REJECT_INDEX",
    "REJECT_CREDENTIAL_PREFIX",
    "REJECT_PUBKEY_MISMATCH",
    "REJECT_SIGNATURE",
)
EXCEPTIONAL = union(*(fix(outcome=outcome) for outcome in EXCEPTIONAL_OUTCOMES))
COVERAGE = coverage_spec(
    "bls_to_execution_change",
    focus="process_bls_to_execution_change: validator index, credential, pubkey, and signature",
    record="one operation",
    aspects=ASPECTS,
    profiles={
        "smoke": OUTCOME.exhaustive(),
        "normal": NORMAL,
        "exceptional": EXCEPTIONAL,
        "standard": union(NORMAL, EXCEPTIONAL),
        "max": exhaustive(FACTORS),
    },
    constraints=SCENARIO_CONSTRAINTS,
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes, backend="python")
