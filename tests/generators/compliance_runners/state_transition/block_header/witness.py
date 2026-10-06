"""Joint slot and assertion witnesses for block-header obligations."""

from functools import cache

from .target import COVERAGE, GATES, HEADER

BUCKET_DELTAS = {"LT_FAR": -2, "LT_1": -1, "EQ": 0, "GT_1": 1, "GT_FAR": 2}


@cache
def _configurations():
    return tuple(
        dict(configuration)
        for configuration in COVERAGE.model().configurations()
        if COVERAGE.feasible(dict(configuration))
    )


def complete_obligation(obligation):
    """Preserve requested values and prefer the fewest failing assertions."""
    candidates = [
        assignment
        for assignment in _configurations()
        if all(assignment.get(name) == value for name, value in obligation.items())
    ]
    if not candidates:
        raise ValueError(f"no feasible block-header completion for {obligation}")
    return min(
        candidates,
        key=lambda assignment: (
            sum(not gate.holds(assignment[gate.name]) for gate in GATES),
            repr(sorted(assignment.items())),
        ),
    ).copy()


def slot_witness(assignment):
    """Choose non-negative slots with latest header no later than the state."""
    state_slot = 4
    match_delta = BUCKET_DELTAS[assignment["slot_matches_state"]]
    newer_delta = BUCKET_DELTAS[assignment["slot_is_newer"]]
    # Far buckets contain several distances. Keep the latest header strictly
    # before the state when both far buckets permit it, isolating stale/future
    # block failures from a duplicate-header failure after repairing the slot.
    if match_delta == newer_delta and abs(match_delta) == 2:
        if match_delta < 0:
            match_delta -= 1
        else:
            newer_delta += 1
    block_slot = state_slot + match_delta
    latest_header_slot = block_slot - newer_delta
    if not 0 <= latest_header_slot <= state_slot or block_slot < 0:
        raise ValueError("slot buckets have no valid-state witness")
    assert (
        HEADER["slot_matches_state"].abstract(block_slot - state_slot)
        == assignment["slot_matches_state"]
    )
    assert (
        HEADER["slot_is_newer"].abstract(block_slot - latest_header_slot)
        == assignment["slot_is_newer"]
    )
    return state_slot, block_slot, latest_header_slot
