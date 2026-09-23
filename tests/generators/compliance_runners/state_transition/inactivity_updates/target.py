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

from itertools import combinations

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
    each,
    exhaustive,
    factor,
    Integer,
    union,
)

from .observation import observe_attributes

current_epoch = attribute("current_epoch", Integer(min=0))
loop_reached = attribute("loop_reached", Boolean())
any_slashed = attribute("any_slashed", Boolean())
eligible_count = attribute("eligible_count", Integer(min=0))
ineligible_count = attribute("ineligible_count", Integer(min=0))
active_eligible_count = attribute("active_eligible_count", Integer(min=0))
slashed_count = attribute("slashed_count", Integer(min=0))
max_slashed_withdrawable = attribute("max_slashed_withdrawable", Integer(min=0))
previous_epoch_plus_one = attribute("previous_epoch_plus_one", Integer(min=0))
loop_nonempty = attribute("loop_nonempty", Boolean())
post_present = attribute("post_present", Boolean())
participating_count = attribute("participating_count", Integer(min=0))
zero_score_count = attribute("zero_score_count", Integer(min=0))
finality_delay = attribute("finality_delay", Integer(min=0))
changed_score_count = attribute("changed_score_count", Integer(min=0))

genesis_epoch = constant("genesis_epoch", Integer(min=0))
min_epochs_to_inactivity_penalty = constant("min_epochs_to_inactivity_penalty", Integer(min=0))
COUNTS = ("ZERO", "ONE", "MANY")
BRANCH_MIX = ("ALL_INCREMENT", "ALL_DECREMENT", "MIXED")
AFTER_GENESIS = comparison("current_after_genesis", current_epoch, genesis_epoch, op=">")
METHOD = aspect("method", AFTER_GENESIS)
ELIGIBLE_COUNT = categorical(
    "eligible_validators",
    choose(eligible_count == 0, "ZERO", choose(eligible_count == 1, "ONE", "MANY")),
    COUNTS,
    when=AFTER_GENESIS,
)
HAS_SLASHED = factor("has_slashed_validators", slashed_count > 0, when=AFTER_GENESIS)
ELIGIBLE = aspect(
    "eligible",
    ELIGIBLE_COUNT,
    factor("has_ineligible_validators", ineligible_count > 0, when=AFTER_GENESIS),
    factor("has_active_eligible", active_eligible_count > 0, when=AFTER_GENESIS),
    HAS_SLASHED,
    comparison(
        "slashed_withdrawable_vs_previous",
        max_slashed_withdrawable,
        previous_epoch_plus_one,
        op=">",
        when=HAS_SLASHED,
    ),
)
LOOP = aspect(
    "loop",
    categorical(
        "branch_mix",
        choose(
            participating_count == 0,
            "ALL_INCREMENT",
            choose(participating_count == eligible_count, "ALL_DECREMENT", "MIXED"),
        ),
        BRANCH_MIX,
        when=ELIGIBLE_COUNT != "ZERO",
    ),
    comparison(
        "leaking",
        finality_delay,
        min_epochs_to_inactivity_penalty,
        op=">",
        when=ELIGIBLE_COUNT != "ZERO",
    ),
    factor("has_zero_score_eligible", zero_score_count > 0, when=ELIGIBLE_COUNT != "ZERO"),
    factor(
        "scores_changed",
        changed_score_count > 0,
        when=ELIGIBLE_COUNT != "ZERO",
        available_when=post_present,
    ),
)
ASPECTS = (METHOD, ELIGIBLE, LOOP)
ALL_FACTORS = [f for a in ASPECTS for f in a.declarations]
LOOP_GATED = tuple(f.name for f in LOOP.factors)
_GT = ("GT", "GT_1", "GT_FAR", True)


def _epoch_never_before_genesis(a: dict, _g: str) -> bool:
    return a.get("current_after_genesis") not in ("LT", "LT_1", "LT_FAR")


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


FEASIBLE = rules(
    _epoch_never_before_genesis,
    _empty_loop_has_no_body,
    _mixed_branches_need_two_validators,
    _eligible_needs_a_disjunct,
)

BRANCHES = exhaustive(LOOP.declarations[:3])
EFFECT = exhaustive([LOOP.declarations[0], LOOP.declarations[3]])
PROFILES = {
    "smoke": each(ALL_FACTORS),
    "method": METHOD.exhaustive(),
    "eligible": ELIGIBLE.exhaustive(),
    "loop": union(BRANCHES, EFFECT),
    "standard": union(
        each(ALL_FACTORS), *(a.each() * b.each() for a, b in combinations(ASPECTS, 2))
    ),
}
COVERAGE = coverage_spec(
    "inactivity_updates",
    focus="genesis guard, eligible-set shape, and branch mix and effects across loop iterations",
    record="one vector; loop body details are covered by inactivity_updates_loop",
    attributes=(
        current_epoch,
        loop_reached,
        any_slashed,
        eligible_count,
        ineligible_count,
        active_eligible_count,
        slashed_count,
        max_slashed_withdrawable,
        previous_epoch_plus_one,
        loop_nonempty,
        post_present,
        participating_count,
        zero_score_count,
        finality_delay,
        changed_score_count,
    ),
    constants=(genesis_epoch, min_epochs_to_inactivity_penalty),
    aspects=ASPECTS,
    profiles=PROFILES,
    feasible=FEASIBLE,
)
TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "genesis_epoch": lambda spec: int(spec.GENESIS_EPOCH),
        "min_epochs_to_inactivity_penalty": lambda spec: int(spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY),
    },
)
