"""Coverage declaration for Gloas ``process_attestation``."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    coverage_spec,
    dimension,
    exhaustive,
    fix,
    implies,
    union,
)

from .observation import observe_attributes

GATE_NAMES = (
    "target_epoch_in_window",
    "target_epoch_matches_slot",
    "inclusion_delay_ok",
    "index_valid",
    "committee_indices_valid",
    "committee_nonempty",
    "aggregation_length_valid",
    "signature_valid",
)
INPUT_NAMES = (
    *GATE_NAMES,
    "target_is_current",
    "attestation_is_same_slot",
    "pending_payment_amount_positive",
    "sets_new_participation_flag",
)
inputs = {name: attribute(f"observed_{name}", Boolean()) for name in INPUT_NAMES}
flags = {name: dimension(name, value) for name, value in inputs.items()}
window, matches, delay, index, committees, nonempty, length, signature = (
    flags[name] for name in GATE_NAMES
)
current, same_slot, payment_positive, new_flag = (flags[name] for name in INPUT_NAMES[8:])
REJECTS = (
    "REJECT_TARGET_EPOCH_OUT_OF_WINDOW",
    "REJECT_TARGET_EPOCH_SLOT_MISMATCH",
    "REJECT_INCLUSION_DELAY",
    "REJECT_INDEX",
    "REJECT_COMMITTEE_INDEX",
    "REJECT_COMMITTEE_EMPTY",
    "REJECT_AGGREGATION_LENGTH",
    "REJECT_SIGNATURE",
)
outcome = dimension(
    "outcome",
    choose(
        *((~inputs[name], reject) for name, reject in zip(GATE_NAMES, REJECTS, strict=True)),
        choose(inputs["target_is_current"], "ACCEPT_CURRENT", no="ACCEPT_PREVIOUS"),
    ),
)
effect = dimension(
    "payment_weight_increased", attribute("observed_payment_weight_increased", Boolean())
)
accepted = dimension("accepted", attribute("observed_accepted", Boolean()))
DATA = aspect("data", window, matches, delay, index)
COMMITTEES = aspect("committees", committees, nonempty, length)
SIGNATURE = aspect("signature", signature)
PAYMENT = aspect("builder_payment", same_slot, payment_positive, new_flag)
OUTCOME = aspect("outcome", current, effect, outcome, accepted)
INPUT_ASPECTS = (DATA, COMMITTEES, SIGNATURE, PAYMENT)
ASPECTS = (*INPUT_ASPECTS, OUTCOME)
FACTORS = tuple(f for a in ASPECTS for f in a.declarations)

NORMAL_GATES = fix(**dict.fromkeys(GATE_NAMES, True))
NORMAL = union(
    *(a.exhaustive() * b.exhaustive() * NORMAL_GATES for a, b in combinations(INPUT_ASPECTS, 2)),
    OUTCOME.exhaustive() * NORMAL_GATES,
)


def single_fault(gate):
    """Keep other applicable checks passing, without constraining bypassed ones.

    Window membership guards the slot/target fault. Indexing, committee
    resolution, nonempty aggregation, and length form a structural dependency
    chain for fault counting; delay and index remain independent of the window.
    """
    values = dict.fromkeys(GATE_NAMES, True)
    values[gate] = False
    if gate == "target_epoch_in_window":
        del values["target_epoch_matches_slot"]
    if gate in GATE_NAMES[3:]:
        for later in GATE_NAMES[GATE_NAMES.index(gate) + 1 :]:
            del values[later]
    return fix(**values)


EXCEPTIONAL = OUTCOME.exhaustive() * union(*(single_fault(name) for name in GATE_NAMES))
COVERAGE = coverage_spec(
    "attestation",
    focus="process_attestation: data, committee structure, signatures, and same-slot builder payment",
    record="one operation",
    aspects=ASPECTS,
    constraints=(
        implies(same_slot, all_of(current, matches, delay)),
        implies(~delay & matches, current),
        implies(~delay & ~matches, ~current),
        implies(~same_slot, ~payment_positive & ~new_flag),
        implies(~window, ~current & ~matches),
        implies(~committees, all_of(~nonempty, ~length, ~signature)),
        implies(~nonempty, ~signature),
        implies(~length, ~signature),
        implies(
            ~signature | ~committees | ~nonempty | ~length | ~index, ~payment_positive & ~new_flag
        ),
        outcome
        == choose(
            *((~flags[name], reject) for name, reject in zip(GATE_NAMES, REJECTS, strict=True)),
            choose(current, "ACCEPT_CURRENT", no="ACCEPT_PREVIOUS"),
        ),
        accepted == all_of(*(flags[name] for name in GATE_NAMES)),
        effect == all_of(accepted, same_slot, payment_positive, new_flag),
    ),
    profiles={
        "smoke": exhaustive((outcome,)),
        "normal": NORMAL,
        "exceptional": EXCEPTIONAL,
        "standard": union(NORMAL, EXCEPTIONAL),
        # The complete finite space strengthens the former bounded-fault max.
        "max": exhaustive(FACTORS),
    },
)

TARGET = bind(COVERAGE, observe_attributes=observe_attributes)
