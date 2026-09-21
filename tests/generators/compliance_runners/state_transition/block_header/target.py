"""Coverage target for the assertion slice of Gloas ``process_block_header``.

The operation vectors provide a ``BeaconBlock`` in
``block_header.ssz_snappy``. Signature verification and the rest of
``process_block`` are intentionally out of scope.
"""

# ruff: noqa: F841 - factor declarations are assignments the body never reads
from __future__ import annotations

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    ACCEPTED,
    capture_observations,
    capture_outcome,
    CAttribute,
    CFactor,
    CGate,
    coverage_aspect,
    CPred,
    each,
    fix,
    nwise,
    nwise_of,
    rules,
    Target,
    union,
)


@coverage_aspect("header")
def capture_header(
    proposer_found: CGate,
    block_slot: CAttribute[int],
    state_slot: CAttribute[int],
    latest_header_slot: CAttribute[int],
    proposer_index: CAttribute[int],
    expected_proposer_index: CAttribute[int],
    parent_root_match: CAttribute[bool],
    proposer_slashed: CAttribute[bool],
):
    slot_matches_state: CFactor = block_slot == state_slot
    slot_is_newer: CFactor = block_slot > latest_header_slot
    proposer_index_matches: CFactor = proposer_index == expected_proposer_index
    parent_matches: CPred = parent_root_match
    if proposer_found:
        proposer_not_slashed: CPred = not proposer_slashed


HEADER = capture_header
ASPECTS = (HEADER, capture_outcome)
GATES = [
    HEADER["slot_matches_state"],
    HEADER["slot_is_newer"],
    HEADER["proposer_index_matches"],
    HEADER["parent_matches"],
    HEADER["proposer_not_slashed"],
]


def observe(ctx) -> None:
    spec, state, block = ctx.spec, ctx.pre, ctx.operation
    proposer_index = int(block.proposer_index)
    proposer_found = proposer_index < len(state.validators)
    capture_observations(proposer_found)
    capture_header(
        proposer_found,
        block_slot=int(block.slot),
        state_slot=int(state.slot),
        latest_header_slot=int(state.latest_block_header.slot),
        proposer_index=proposer_index,
        expected_proposer_index=int(spec.get_beacon_proposer_index(state)),
        parent_root_match=block.parent_root == spec.hash_tree_root(state.latest_block_header),
        proposer_slashed=bool(state.validators[proposer_index].slashed)
        if proposer_found
        else False,
    )


def _holds(assignment: dict, factor, granularity: str) -> bool | None:
    return (
        None
        if factor.name not in assignment
        else factor.holds(assignment[factor.name], granularity)
    )


def _accepted_iff_all_assertions_hold(assignment: dict, granularity: str) -> bool:
    accepted = _holds(assignment, ACCEPTED, granularity)
    if accepted is None:
        return True
    assertions = [_holds(assignment, factor, granularity) for factor in GATES]
    if accepted:
        return all(value is not False for value in assertions)
    return not all(value is True for value in assertions)


FEASIBLE = rules(_accepted_iff_all_assertions_hold)
NORMAL = fix(accepted=True)
EXCEPTIONAL = fix(accepted=False)

PROFILES = {
    "smoke": each([*HEADER.factors, ACCEPTED]).where(FEASIBLE),
    "normal": (NORMAL * HEADER.exhaustive()).where(FEASIBLE),
    "exceptional": (EXCEPTIONAL * nwise(HEADER.factors, 2)).where(FEASIBLE),
    "standard": union(
        each([*HEADER.factors, ACCEPTED]),
        nwise_of([HEADER.each(), capture_outcome.each()], 2),
    ).where(FEASIBLE),
}

TARGET = Target("block_header", ASPECTS, observe, PROFILES, FEASIBLE)
