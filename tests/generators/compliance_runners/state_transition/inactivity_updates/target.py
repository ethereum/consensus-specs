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

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    any_of,
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    comparison,
    constant,
    count,
    coverage_spec,
    dimension,
    each,
    exhaustive,
    implies,
    Integer,
    nwise,
    present,
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
ELIGIBLE_COUNT = dimension("eligible_validators", count(eligible_count), when=AFTER_GENESIS)
HAS_SLASHED = dimension("has_slashed_validators", slashed_count > 0, when=AFTER_GENESIS)
ELIGIBLE = aspect(
    "eligible",
    ELIGIBLE_COUNT,
    dimension("has_ineligible_validators", ineligible_count > 0, when=AFTER_GENESIS),
    dimension("has_active_eligible", active_eligible_count > 0, when=AFTER_GENESIS),
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
    dimension(
        "branch_mix",
        choose(
            (participating_count == 0, "ALL_INCREMENT"),
            (participating_count == eligible_count, "ALL_DECREMENT"),
            "MIXED",
        ),
        when=ELIGIBLE_COUNT != "ZERO",
    ),
    comparison(
        "leaking",
        finality_delay,
        min_epochs_to_inactivity_penalty,
        op=">",
        when=ELIGIBLE_COUNT != "ZERO",
    ),
    dimension("has_zero_score_eligible", zero_score_count > 0, when=ELIGIBLE_COUNT != "ZERO"),
    dimension(
        "scores_changed",
        changed_score_count > 0,
        when=ELIGIBLE_COUNT != "ZERO",
        available_when=post_present,
    ),
)
ASPECTS = (METHOD, ELIGIBLE, LOOP)
ALL_FACTORS = [f for a in ASPECTS for f in a.declarations]
HAS_ACTIVE = ELIGIBLE.ref("has_active_eligible")
HAS_INELIGIBLE = ELIGIBLE.ref("has_ineligible_validators")
UNWITHDRAWABLE = ELIGIBLE.ref("slashed_withdrawable_vs_previous")
BRANCH = LOOP.ref("branch_mix")
LEAKING = LOOP.ref("leaking")
ZERO_SCORE = LOOP.ref("has_zero_score_eligible")
CHANGED = LOOP.ref("scores_changed")

CONSTRAINTS = (
    implies(
        ELIGIBLE_COUNT == "ZERO",
        all_of(~any_of(*(present(f) for f in LOOP.declarations)), ~HAS_ACTIVE, ~UNWITHDRAWABLE),
    ),
    implies(ELIGIBLE_COUNT == "ONE", BRANCH != "MIXED"),
    implies(ELIGIBLE_COUNT != "ZERO", any_of(HAS_ACTIVE, HAS_SLASHED & UNWITHDRAWABLE)),
    # The genesis state has a fixed 64-validator set in this materializer.
    implies(~HAS_INELIGIBLE, present(ELIGIBLE_COUNT) & (ELIGIBLE_COUNT == "MANY")),
    implies((ELIGIBLE_COUNT == "ONE") & ZERO_SCORE & CHANGED, LEAKING),
    implies(~CHANGED, ZERO_SCORE & ~LEAKING),
    implies((ELIGIBLE_COUNT == "ONE") & ZERO_SCORE & CHANGED, BRANCH != "ALL_DECREMENT"),
    implies(~HAS_ACTIVE, BRANCH == "ALL_INCREMENT"),
    implies(HAS_SLASHED & UNWITHDRAWABLE, BRANCH != "ALL_DECREMENT"),
    implies(~HAS_INELIGIBLE & HAS_SLASHED, BRANCH != "ALL_DECREMENT"),
)

BRANCHES = exhaustive(LOOP.declarations[:3])
EFFECT = exhaustive([LOOP.declarations[0], LOOP.declarations[3]])
PROFILES = {
    "smoke": each(ALL_FACTORS),
    "max": union(METHOD.exhaustive(), ELIGIBLE.exhaustive(), nwise(ALL_FACTORS, 3)),
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
    constraints=CONSTRAINTS,
)
TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "genesis_epoch": lambda spec: int(spec.GENESIS_EPOCH),
        "min_epochs_to_inactivity_penalty": lambda spec: int(spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY),
    },
)
