"""Joint slot boundaries preserve valid prestates and assertion ordering."""

import traceback
from itertools import product
from random import Random
from types import SimpleNamespace

import pytest

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    score,
)

from .coverage import build_profile
from .materializer import BlockHeaderMaterializer
from .target import HEADER, TARGET
from .witness import BUCKET_DELTAS, complete_obligation

BUCKETS = tuple(BUCKET_DELTAS)
REACHABLE_PAIRS = [(match, newer) for i, match in enumerate(BUCKETS) for newer in BUCKETS[i:]]


def materialize(spec, assignment):
    materializer = BlockHeaderMaterializer(spec)
    materializer.rng = Random(124)
    meta, parts = materializer.materialize_solution(SimpleNamespace(**assignment))
    encoded = {name: data for name, _, data in parts}
    pre = spec.BeaconState.decode_bytes(encoded["pre"])
    block = spec.BeaconBlock.decode_bytes(encoded["block_header"])
    post = spec.BeaconState.decode_bytes(encoded["post"]) if "post" in encoded else None
    return meta, pre, block, post


def first_assertion(spec, pre, block):
    with pytest.raises(AssertionError) as error:
        spec.process_block_header(pre.copy(), block)
    frames = traceback.extract_tb(error.value.__traceback__)
    return next(frame.line for frame in reversed(frames) if frame.name == "process_block_header")


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
@pytest.mark.parametrize(("match", "newer"), REACHABLE_PAIRS)
def test_joint_slot_boundaries(preset, match, newer):
    spec = spec_targets[preset]["gloas"]
    accepted = match == "EQ" and newer in ("GT_1", "GT_FAR")
    assignment = {
        "slot_matches_state": match,
        "slot_is_newer": newer,
        "proposer_index_matches": True,
        "parent_matches": True,
        "proposer_not_slashed": True,
        "accepted": accepted,
    }
    meta, pre, block, post = materialize(spec, assignment)
    assert int(pre.latest_block_header.slot) <= int(pre.slot)
    if pre.latest_block_header.slot == pre.slot:
        assert pre.latest_block_header.state_root == spec.Root()
    target = TARGET.for_spec(spec)
    actual = target.record(target.observation(Context(spec, pre, block, post, {})))
    assert actual == meta["claimed"] == assignment
    assert target.feasible(actual)
    if accepted:
        expected = pre.copy()
        spec.process_block_header(expected, block)
        assert post == expected
    else:
        assert post is None
        expected = (
            "assert block.slot == state.slot"
            if match != "EQ"
            else "assert block.slot > state.latest_block_header.slot"
        )
        assert first_assertion(spec, pre, block) == expected


@pytest.mark.parametrize(
    "gate", ["proposer_index_matches", "parent_matches", "proposer_not_slashed"]
)
def test_later_assertions_remain_isolated(gate):
    spec = spec_targets["minimal"]["gloas"]
    assignment = complete_obligation(
        {
            "slot_matches_state": "EQ",
            "slot_is_newer": "GT_1",
            gate: False,
            "accepted": False,
        }
    )
    meta, pre, block, post = materialize(spec, assignment)
    target = TARGET.for_spec(spec)
    actual = target.record(target.observation(Context(spec, pre, block, post, {})))
    assert actual == meta["claimed"] == assignment
    assert post is None
    expected = {
        "proposer_index_matches": "assert block.proposer_index == get_beacon_proposer_index(state)",
        "parent_matches": "assert block.parent_root == hash_tree_root(state.latest_block_header)",
        "proposer_not_slashed": "assert not proposer.slashed",
    }[gate]
    assert first_assertion(spec, pre, block) == expected


def test_impossible_pairs_and_contradictory_acceptance_are_rejected():
    for match, newer in product(BUCKETS, repeat=2):
        if (match, newer) not in REACHABLE_PAIRS:
            with pytest.raises(ValueError, match="no feasible"):
                complete_obligation({"slot_matches_state": match, "slot_is_newer": newer})
    with pytest.raises(ValueError, match="no feasible"):
        complete_obligation({"slot_matches_state": "GT_1", "accepted": True})
    with pytest.raises(ValueError, match="no feasible"):
        complete_obligation(
            {
                name: (
                    "EQ"
                    if name == "slot_matches_state"
                    else "GT_1"
                    if name == "slot_is_newer"
                    else True
                )
                for name in (
                    "slot_matches_state",
                    "slot_is_newer",
                    "proposer_index_matches",
                    "parent_matches",
                    "proposer_not_slashed",
                )
            }
            | {"accepted": False}
        )


@pytest.mark.parametrize("profile", ["smoke", "normal", "exceptional", "standard", "max"])
def test_materialized_profiles_cover_their_obligations(profile):
    spec = spec_targets["minimal"]["gloas"]
    target = TARGET.for_spec(spec)
    _, representatives = build_profile(profile, spec=spec)
    records = []
    for assignment in representatives:
        meta, pre, block, post = materialize(spec, assignment)
        record = target.record(target.observation(Context(spec, pre, block, post, {})))
        assert record == meta["claimed"]
        assert all(record[name] == value for name, value in assignment.items())
        records.append(record)
    report = score(target, records, target.profiles[profile])
    assert report.covered == report.total
    assert report.uncovered == report.unexpected == []
    assert HEADER["proposer_index_matches"].granularity == "predicate"
