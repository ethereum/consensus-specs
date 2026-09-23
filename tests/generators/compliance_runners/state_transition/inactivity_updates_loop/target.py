"""Coverage target for the ``process_inactivity_updates`` loop body.

A coverage record is per vector, not per iteration, so per-validator factors are
only well defined when the loop runs exactly once.  Every factor here is gated
on ``single_eligible``; vectors with zero or several eligible indices satisfy
nothing in this target, which is the intended signal — the set-level properties
are scored by the ``inactivity_updates`` target instead.

The body is two branches over one validator:

    if index in get_unslashed_participating_indices(...):
        state.inactivity_scores[index] -= min(1, state.inactivity_scores[index])
    else:
        state.inactivity_scores[index] += INACTIVITY_SCORE_BIAS
    if not is_in_inactivity_leak(state):
        state.inactivity_scores[index] -= min(
            INACTIVITY_SCORE_RECOVERY_RATE, state.inactivity_scores[index]
        )

Both ``min`` saturations and ``is_in_inactivity_leak``'s own comparison are
declared as comparison factors, so a ``cmp3`` or ``cmp5`` run demands the
boundary cases (score exactly zero, score exactly at the recovery rate, finality
delay exactly at ``MIN_EPOCHS_TO_INACTIVITY_PENALTY``) rather than only the
two sides of each branch.

Bind ``TARGET.for_spec(spec)`` before enumerating profiles: recovery-boundary
and score-increase feasibility depend on that spec's configured constants.
"""

# ruff: noqa: F841 - factor declarations are assignments the body never reads
from __future__ import annotations

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    capture_observations,
    CAttribute,
    CConstant,
    CEnum,
    CFactor,
    CGate,
    Context,
    coverage_aspect,
    CPred,
    each,
    exhaustive,
    nwise,
    rules,
    Target,
    union,
)

from .observation import observe_attributes

DELTAS = ("DECREASED", "UNCHANGED", "INCREASED")

# --- aspects ------------------------------------------------------------------


@coverage_aspect("body")
def capture_body(
    single_eligible: CGate,
    leak_free: CGate,
    post_present: CGate,
    score: CAttribute[int],
    post_score: CAttribute[int],
    participating: CAttribute[bool],
    slashed: CAttribute[bool],
    active_in_previous: CAttribute[bool],
    timely_target_flag: CAttribute[bool],
    finality_delay: CAttribute[int],
    *,
    min_epochs_to_inactivity_penalty: CConstant[int],
    bias: CConstant[int],
    recovery_rate: CConstant[int],
):
    """One iteration of the loop, for the single eligible validator."""
    if single_eligible:
        # why the index is eligible at all.  The withdrawable-epoch boundary is
        # *not* a factor here: an index this loop visits is eligible, so
        # `previous_epoch + 1 < withdrawable_epoch` already holds for every
        # slashed one, and the comparison could only ever read GT.  The
        # boundary lives in the `inactivity_updates` target, over all slashed
        # validators, where the excluded side of it exists.
        is_active_in_previous: CPred = active_in_previous
        is_slashed: CPred = slashed
        # which branch the participation check takes, and why
        has_target_flag: CPred = timely_target_flag
        is_participating: CPred = participating
        # min(1, score)
        score_gt_zero: CFactor = score > 0
        # is_in_inactivity_leak(state)
        leaking: CFactor = finality_delay > min_epochs_to_inactivity_penalty
        score_after_participation = max(0, score - 1) if participating else score + bias
        if leak_free:
            # min(INACTIVITY_SCORE_RECOVERY_RATE, score)
            score_vs_recovery_rate: CFactor = score_after_participation > recovery_rate
        if post_present:
            score_delta: CEnum[DELTAS] = (
                "DECREASED"
                if post_score < score
                else "UNCHANGED"
                if post_score == score
                else "INCREASED"
            )


BODY = capture_body
ASPECTS = (BODY,)
ALL_FACTORS = list(BODY.factors)

# --- observation --------------------------------------------------------------


def observe(ctx: Context) -> None:
    attributes = observe_attributes(ctx)
    capture_observations(**attributes)
    capture_body(**attributes)


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

    return rules(zero_score_recovery, leak_free_cannot_gain)


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


FEASIBLE = rules(
    _score_is_never_negative,
    _participation_is_unslashed_flagged_and_active,
    _eligible_needs_a_disjunct,
    _recovery_applies_only_when_leak_free,
    _participants_never_gain_score,
    _zero_score_participant_is_unchanged,
    _leaking_non_participant_gains_score,
)

# --- profiles -----------------------------------------------------------------

# why the index is in the loop at all
MEMBERSHIP = exhaustive(
    [
        BODY["is_active_in_previous"],
        BODY["is_slashed"],
        BODY["has_target_flag"],
    ]
)
# The two branches and both min() saturations. `score_vs_recovery_rate` sits
# behind the leak-free gate, so a single exhaustive formula over all four
# factors would mention it in every obligation and never ask for a leaking
# vector at all; the two halves are enumerated separately instead.
ARITHMETIC = union(
    exhaustive([BODY["is_participating"], BODY["score_gt_zero"], BODY["leaking"]]),
    exhaustive([BODY["is_participating"], BODY["score_gt_zero"], BODY["score_vs_recovery_rate"]]),
)
# the observed score change against the branch that produced it
EFFECTS = each([BODY["score_delta"]]) * each(
    [BODY["is_participating"], BODY["leaking"], BODY["score_gt_zero"]]
)

PROFILES = {
    # every value of every factor
    "smoke": each(ALL_FACTORS).where(FEASIBLE),
    # why this index is eligible, exhaustively
    "membership": MEMBERSHIP.where(FEASIBLE),
    # both branches and both saturations, exhaustively
    "arithmetic": ARITHMETIC.where(FEASIBLE),
    # the post-state effect against the branch that produced it
    "effects": EFFECTS.where(FEASIBLE),
    # the focused profiles plus every pair of body factors
    "standard": union(MEMBERSHIP, ARITHMETIC, EFFECTS, nwise(ALL_FACTORS, 2)).where(FEASIBLE),
}

TARGET = Target(
    "inactivity_updates",
    ASPECTS,
    observe,
    PROFILES,
    FEASIBLE,
    constants={
        "min_epochs_to_inactivity_penalty": lambda spec: int(spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY),
        "bias": lambda spec: int(spec.config.INACTIVITY_SCORE_BIAS),
        "recovery_rate": lambda spec: int(spec.config.INACTIVITY_SCORE_RECOVERY_RATE),
    },
    constant_feasibility=constant_feasibility,
)
