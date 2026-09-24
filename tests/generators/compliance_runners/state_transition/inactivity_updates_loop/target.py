"""One inactivity-update iteration, observed on a singleton eligible set.

Activation prerequisites are included by conditional coverage formulas. Missing
post-state data affects observation availability, not factor activation.
"""

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
    exhaustive,
    factor,
    Integer,
    maximum,
    nwise,
    union,
)

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
SCORE = comparison("score_gt_zero", score, 0)
LEAKING = comparison("leaking", finality_delay, min_epochs_to_inactivity_penalty)
RECOVERY = comparison(
    "score_vs_recovery_rate", score_after_participation, recovery_rate, when=~LEAKING
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


def _holds(a: dict, name: str, g: str) -> bool | None:
    return None if name not in a else BODY[name].holds(a[name], g)


def _score_is_never_negative(a: dict, _g: str) -> bool:
    """``inactivity_scores`` is a ``uint64`` list."""
    return a.get("score_gt_zero") not in ("LT", "LT_1", "LT_FAR")


def _participation_is_unslashed_flagged_and_active(a: dict, _g: str) -> bool:
    """``get_unslashed_participating_indices``: active, flagged, and not slashed."""
    participating = a.get("is_participating")
    if participating is True:
        return not (
            a.get("is_slashed") is True
            or a.get("has_target_flag") is False
            or a.get("is_active_in_previous") is False
        )
    if participating is False:
        # All three conditions met, yet not participating: impossible.
        return not (
            a.get("is_slashed") is False
            and a.get("has_target_flag") is True
            and a.get("is_active_in_previous") is True
        )
    return True


def _eligible_needs_a_disjunct(a: dict, _g: str) -> bool:
    """An index the loop visits is eligible: active, or slashed and not yet withdrawable."""
    return not (a.get("is_active_in_previous") is False and a.get("is_slashed") is False)


def _recovery_applies_only_when_leak_free(a: dict, g: str) -> bool:
    if "score_vs_recovery_rate" not in a:
        return True
    return _holds(a, "leaking", g) is not True


def constant_feasibility(constants: dict):
    """Arithmetic relationships depend on the selected spec's bias and recovery."""
    recovery = constants["recovery_rate"]
    bias = constants["bias"]

    def zero_score_recovery(a: dict, g: str) -> bool:
        if not (
            a.get("is_participating") is True
            and _holds(a, "score_gt_zero", g) is False
            and "score_vs_recovery_rate" in a
        ):
            return True
        # A participant starting at zero has intermediate score zero. Abstract
        # the exact delta, preserving the LT_1/LT_FAR distinction at cmp5.
        expected = BODY["score_vs_recovery_rate"].abstract(-recovery, g)
        return a["score_vs_recovery_rate"] == expected

    def leak_free_cannot_gain(a: dict, g: str) -> bool:
        if recovery < bias or a.get("score_delta") != "INCREASED":
            return True
        # Mentioning the recovery comparison also implies a leak-free branch,
        # even when the partial assignment omits the leaking factor.
        return not (_holds(a, "leaking", g) is False or "score_vs_recovery_rate" in a)

    def recovery_comparison(a: dict, g: str) -> bool:
        if "score_vs_recovery_rate" not in a:
            return True
        if a.get("score_gt_zero") is False and a.get("is_participating") is False:
            return a["score_vs_recovery_rate"] == BODY["score_vs_recovery_rate"].abstract(
                bias - recovery, g
            )
        if a.get("score_delta") == "UNCHANGED" and a.get("score_gt_zero") is True:
            return False
        if a.get("score_delta") == "UNCHANGED" and a.get("score_gt_zero") is False:
            expected = (
                BODY["score_vs_recovery_rate"].abstract(0, g)
                if a.get("is_participating")
                else BODY["score_vs_recovery_rate"].abstract(bias - recovery, g)
            )
            return a["score_vs_recovery_rate"] == expected
        return True

    return rules(zero_score_recovery, leak_free_cannot_gain, recovery_comparison)


def _participants_never_gain_score(a: dict, _g: str) -> bool:
    return not (a.get("is_participating") is True and a.get("score_delta") == "INCREASED")


def _zero_score_participant_is_unchanged(a: dict, g: str) -> bool:
    if not (a.get("is_participating") is True and _holds(a, "score_gt_zero", g) is False):
        return True
    return a.get("score_delta", "UNCHANGED") == "UNCHANGED"


def _leaking_non_participant_gains_score(a: dict, g: str) -> bool:
    """Under a leak the increment is the only write, and the bias is positive."""
    if not (a.get("is_participating") is False and _holds(a, "leaking", g) is True):
        return True
    return a.get("score_delta", "INCREASED") == "INCREASED"


def _positive_score_cannot_be_unchanged(a: dict, _g: str) -> bool:
    return not (a.get("score_gt_zero") is True and a.get("score_delta") == "UNCHANGED")


FEASIBLE = rules(
    _score_is_never_negative,
    _participation_is_unslashed_flagged_and_active,
    _eligible_needs_a_disjunct,
    _recovery_applies_only_when_leak_free,
    _participants_never_gain_score,
    _zero_score_participant_is_unchanged,
    _leaking_non_participant_gains_score,
    _positive_score_cannot_be_unchanged,
    lambda a, g: not (a.get("score_gt_zero") is False and a.get("score_delta") == "DECREASED"),
)

# Coverage choices: activation closure preserves both leaking and recovery branches.
MEMBERSHIP = exhaustive([ACTIVE, SLASHED, FLAGGED])
ARITHMETIC = exhaustive([PARTICIPATING, SCORE, LEAKING, RECOVERY])
EFFECTS = each([DELTA]) * each([PARTICIPATING, LEAKING, SCORE])
PROFILES = {
    "smoke": each(ALL_FACTORS),
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
    feasible=FEASIBLE,
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
