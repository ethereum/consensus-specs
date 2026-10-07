"""One inactivity-update iteration, observed on a singleton eligible set.

Activation prerequisites are included by conditional coverage formulas. Missing
post-state data affects observation availability, not factor activation.
"""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    any_of,
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
    exhaustive,
    factor,
    Integer,
    maximum,
    nwise,
    union,
)

from .cases import arithmetic_witnesses
from .observation import observe_attributes

single_eligible = attribute("single_eligible", Boolean())
leak_free = attribute("leak_free", Boolean())
post_present = attribute("post_present", Boolean())
score = attribute("score", Integer(min=0))
post_score = attribute("post_score", Integer(min=0))
participating = attribute("participating", Boolean())
slashed = attribute("slashed", Boolean())
active_in_previous = attribute("active_in_previous", Boolean())
timely_target_flag = attribute("timely_target_flag", Boolean())
finality_delay = attribute("finality_delay", Integer(min=0))
min_epochs_to_inactivity_penalty = constant("min_epochs_to_inactivity_penalty", Integer(min=0))
bias = constant("bias", Integer(min=1))
recovery_rate = constant("recovery_rate", Integer(min=0))

score_after_participation = derived(
    "score_after_participation",
    choose(participating, maximum(0, score - 1), score + bias),
)

ACTIVE = factor("is_active_in_previous", active_in_previous)
SLASHED = factor("is_slashed", slashed)
FLAGGED = factor("has_target_flag", timely_target_flag)
PARTICIPATING = factor("is_participating", participating)
SCORE = comparison("score_gt_zero", score, 0, granularity="cmp5")
LEAKING = comparison(
    "leaking", finality_delay, min_epochs_to_inactivity_penalty, granularity="cmp5"
)
RECOVERY = comparison(
    "score_vs_recovery_rate",
    score_after_participation,
    recovery_rate,
    when=~LEAKING,
    granularity="cmp5",
)
DELTA = categorical(
    "score_delta",
    choose(post_score < score, "DECREASED", choose(post_score == score, "UNCHANGED", "INCREASED")),
    ("DECREASED", "UNCHANGED", "INCREASED"),
    available_when=post_present,
)
BODY = aspect("body", ACTIVE, SLASHED, FLAGGED, PARTICIPATING, SCORE, LEAKING, RECOVERY, DELTA)
ASPECTS = (BODY,)
ALL_FACTORS = BODY.declarations

# --- feasibility --------------------------------------------------------------


CONSTRAINTS = (
    all_of(ACTIVE, FLAGGED, ~SLASHED) == PARTICIPATING,
    any_of(ACTIVE, SLASHED),
)


def constant_feasibility(constants: dict):
    """Require a concrete extension for each arithmetic bucket assignment."""
    witnesses = arithmetic_witnesses(
        constants["min_epochs_to_inactivity_penalty"],
        constants["bias"],
        constants["recovery_rate"],
        (BODY["score_gt_zero"], BODY["leaking"], BODY["score_vs_recovery_rate"]),
    )
    names = {
        "is_participating",
        "score_gt_zero",
        "leaking",
        "score_vs_recovery_rate",
        "score_delta",
    }

    projections = {}

    def feasible(assignment):
        requested = frozenset((name, value) for name, value in assignment.items() if name in names)
        selected = frozenset(name for name, _ in requested)
        if selected not in projections:
            projections[selected] = {
                frozenset((name, value) for name, value in record if name in selected)
                for record in witnesses
            }
        return requested in projections[selected]

    return feasible


# Coverage choices: activation closure preserves both leaking and recovery branches.
MEMBERSHIP = exhaustive([ACTIVE, SLASHED, FLAGGED])
ARITHMETIC = exhaustive([PARTICIPATING, SCORE, LEAKING, RECOVERY])
EFFECTS = each([DELTA]) * each([PARTICIPATING, LEAKING, SCORE])
PROFILES = {
    "smoke": each(ALL_FACTORS),
    "max": union(MEMBERSHIP, ARITHMETIC, EFFECTS, nwise(ALL_FACTORS, 3)),
    "membership": MEMBERSHIP,
    "arithmetic": ARITHMETIC,
    "effects": EFFECTS,
    "standard": union(MEMBERSHIP, ARITHMETIC, EFFECTS, nwise(ALL_FACTORS, 2)),
}
COVERAGE = coverage_spec(
    "inactivity_updates",
    focus="process_inactivity_updates: loop body",
    record="one eligible validator in a singleton vector",
    applicable_when=single_eligible,
    attributes=(
        single_eligible,
        leak_free,
        post_present,
        score,
        post_score,
        participating,
        slashed,
        active_in_previous,
        timely_target_flag,
        finality_delay,
    ),
    constants=(min_epochs_to_inactivity_penalty, bias, recovery_rate),
    aspects=ASPECTS,
    profiles=PROFILES,
    constraints=CONSTRAINTS,
    constant_feasibility=constant_feasibility,
)
TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "min_epochs_to_inactivity_penalty": lambda spec: int(spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY),
        "bias": lambda spec: int(spec.config.INACTIVITY_SCORE_BIAS),
        "recovery_rate": lambda spec: int(spec.config.INACTIVITY_SCORE_RECOVERY_RATE),
    },
)
