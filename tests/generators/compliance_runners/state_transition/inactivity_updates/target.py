"""Coverage target for ``process_inactivity_updates``: guard and eligible set.

The handler is a genesis guard plus a loop over
``get_eligible_validator_indices``.  This target covers what is a property of
the *set* rather than of one iteration:

  method    ``get_current_epoch(state) == GENESIS_EPOCH`` and the early return
  eligible  the shape of ``get_eligible_validator_indices``: how many indices it
            yields, whether the filter excludes anyone, and which disjunct
            (active in the previous epoch / slashed and not yet withdrawable)
            admits them
  loop      properties that do not exist for a single validator: the mix of
            branches taken across iterations, and whether any score changed

``branch_mix == "MIXED"`` is the obligation that distinguishes a correct loop
from one that applies the first index's branch to every index, so it belongs
here and not in the body target.

The loop body itself is covered by ``inactivity_updates_loop``, on vectors with
exactly one eligible index, where per-validator factors are well defined.
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
    count_class,
    coverage_aspect,
    CPred,
    each,
    exhaustive,
    nwise_of,
    rules,
    Target,
    union,
)

from .observation import observe_attributes

COUNTS = ("ZERO", "ONE", "MANY")
BRANCH_MIX = ("ALL_INCREMENT", "ALL_DECREMENT", "MIXED")

# --- aspects ------------------------------------------------------------------


@coverage_aspect("method")
def capture_method(
    current_epoch: CAttribute[int],
    *,
    genesis_epoch: CConstant[int],
):
    """The guard: the handler returns before the loop at the genesis epoch."""
    current_after_genesis: CFactor = current_epoch > genesis_epoch


@coverage_aspect("eligible")
def capture_eligible(
    loop_reached: CGate,
    any_slashed: CGate,
    eligible_count: CAttribute[int],
    ineligible_count: CAttribute[int],
    active_eligible_count: CAttribute[int],
    slashed_count: CAttribute[int],
    max_slashed_withdrawable: CAttribute[int],
    previous_epoch_plus_one: CAttribute[int],
):
    """``is_active_validator(v, previous_epoch) or (v.slashed and previous_epoch + 1 < v.withdrawable_epoch)``."""
    if loop_reached:
        eligible_validators: CEnum[COUNTS] = count_class(eligible_count)
        has_ineligible_validators: CPred = ineligible_count > 0
        has_active_eligible: CPred = active_eligible_count > 0
        has_slashed_validators: CPred = slashed_count > 0
        if any_slashed:
            # Over the slashed validators, the maximum withdrawable epoch: the
            # comparison holds exactly when the slashed disjunct admits someone.
            slashed_withdrawable_vs_previous: CFactor = (
                max_slashed_withdrawable > previous_epoch_plus_one
            )


@coverage_aspect("loop")
def capture_loop(
    loop_nonempty: CGate,
    post_present: CGate,
    eligible_count: CAttribute[int],
    participating_count: CAttribute[int],
    zero_score_count: CAttribute[int],
    finality_delay: CAttribute[int],
    changed_score_count: CAttribute[int],
    *,
    min_epochs_to_inactivity_penalty: CConstant[int],
):
    """Loop-wide branch mix and effect."""
    if loop_nonempty:
        branch_mix: CEnum[BRANCH_MIX] = (
            "ALL_INCREMENT"
            if participating_count == 0
            else "ALL_DECREMENT"
            if participating_count == eligible_count
            else "MIXED"
        )
        leaking: CFactor = finality_delay > min_epochs_to_inactivity_penalty
        has_zero_score_eligible: CPred = zero_score_count > 0
        if post_present:
            scores_changed: CPred = changed_score_count > 0


METHOD, ELIGIBLE, LOOP = capture_method, capture_eligible, capture_loop
ASPECTS = (METHOD, ELIGIBLE, LOOP)
ALL_FACTORS = [factor for aspect in ASPECTS for factor in aspect.factors]

ELIGIBLE_GATED = tuple(f.name for f in ELIGIBLE.factors)
LOOP_GATED = tuple(f.name for f in LOOP.factors)
GATED = ELIGIBLE_GATED + LOOP_GATED

# --- observation --------------------------------------------------------------


def observe(ctx: Context) -> None:
    attributes = observe_attributes(ctx)
    capture_observations(**attributes)
    for aspect in (capture_method, capture_eligible, capture_loop):
        aspect(**{name: attributes[name] for name in aspect.attributes})


# --- feasibility --------------------------------------------------------------

_GT = ("GT", "GT_1", "GT_FAR", True)


def _epoch_never_before_genesis(a: dict, _g: str) -> bool:
    return a.get("current_after_genesis") not in ("LT", "LT_1", "LT_FAR")


def _loop_factors_need_post_genesis(a: dict, g: str) -> bool:
    value = a.get("current_after_genesis")
    if value is not None and METHOD["current_after_genesis"].holds(value, g) is False:
        return not any(name in a for name in GATED)
    return True


def _empty_loop_has_no_body(a: dict, _g: str) -> bool:
    if a.get("eligible_validators") != "ZERO":
        return True
    if any(name in a for name in LOOP_GATED):
        return False
    if a.get("has_active_eligible") is True:
        return False
    # A slashed validator past the withdrawable boundary is itself eligible.
    return a.get("slashed_withdrawable_vs_previous") not in _GT


def _mixed_branches_need_two_validators(a: dict, _g: str) -> bool:
    return not (a.get("eligible_validators") == "ONE" and a.get("branch_mix") == "MIXED")


def _eligible_needs_a_disjunct(a: dict, _g: str) -> bool:
    """Nobody is eligible without an active validator or a slashed, un-withdrawable one."""
    if a.get("eligible_validators") not in ("ONE", "MANY"):
        return True
    if a.get("has_active_eligible") is not False:
        return True
    if a.get("has_slashed_validators") is False:
        return False
    value = a.get("slashed_withdrawable_vs_previous")
    return value is None or value in _GT


def _slashed_boundary_needs_a_slashed_validator(a: dict, _g: str) -> bool:
    if "slashed_withdrawable_vs_previous" not in a:
        return True
    return a.get("has_slashed_validators") is not False


FEASIBLE = rules(
    _epoch_never_before_genesis,
    _loop_factors_need_post_genesis,
    _empty_loop_has_no_body,
    _mixed_branches_need_two_validators,
    _eligible_needs_a_disjunct,
    _slashed_boundary_needs_a_slashed_validator,
)

# --- profiles -----------------------------------------------------------------

# An exhaustive formula over a whole aspect would mention every factor in every
# obligation, and a factor behind a narrower gate then forces that gate true
# everywhere: an exhaustive `eligible` never asks for a state without a slashed
# validator. Enumerate the unconditional factors and the gated one separately.
ELIGIBLE_SHAPE = exhaustive(
    [
        ELIGIBLE["eligible_validators"],
        ELIGIBLE["has_ineligible_validators"],
        ELIGIBLE["has_active_eligible"],
        ELIGIBLE["has_slashed_validators"],
    ]
)
SLASHED_BOUNDARY = exhaustive(
    [
        ELIGIBLE["eligible_validators"],
        ELIGIBLE["has_active_eligible"],
        ELIGIBLE["slashed_withdrawable_vs_previous"],
    ]
)
BRANCHES = exhaustive([LOOP["branch_mix"], LOOP["leaking"], LOOP["has_zero_score_eligible"]])
EFFECT = exhaustive([LOOP["branch_mix"], LOOP["scores_changed"]])

PROFILES = {
    # every value of every factor
    "smoke": each(ALL_FACTORS).where(FEASIBLE),
    # the guard on its own
    "method": METHOD.exhaustive().where(FEASIBLE),
    # set size against each eligibility disjunct, and the withdrawable boundary
    "eligible": union(ELIGIBLE_SHAPE, SLASHED_BOUNDARY).where(FEASIBLE),
    # every branch mix against the leak boundary and against the observed effect
    "loop": union(BRANCHES, EFFECT).where(FEASIBLE),
    # each aspect on its own, then aspects pairwise against each other's values
    "standard": union(
        each(ALL_FACTORS),
        nwise_of([METHOD.each(), ELIGIBLE.each(), LOOP.each()], 2),
    ).where(FEASIBLE),
}

TARGET = Target(
    "inactivity_updates",
    ASPECTS,
    observe,
    PROFILES,
    FEASIBLE,
    constants={
        "genesis_epoch": lambda spec: int(spec.GENESIS_EPOCH),
        "min_epochs_to_inactivity_penalty": lambda spec: int(spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY),
    },
)
