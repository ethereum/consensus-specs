"""Regression checks for slashed validators in the old lookahead."""

from random import Random
from types import SimpleNamespace

import pytest

from eth_consensus_specs.gloas import minimal as spec
from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context

from .materializer import ProposerLookaheadMaterializer
from .target import TARGET


@pytest.mark.parametrize("tail_matches", [True, False])
def test_slashed_active_validator_is_absent_from_old_lookahead(tail_matches):
    solution = SimpleNamespace(
        fewer_candidates_than_slots="LT_1",
        has_slashed_active_validator=True,
        old_lookahead_contains_slashed=False,
        new_epoch_repeats_old_tail=tail_matches,
    )
    materializer = ProposerLookaheadMaterializer(spec)
    materializer.rng = Random(0)
    _, parts = materializer.materialize_solution(solution)
    pre = spec.BeaconState.decode_bytes(parts[0][2])
    post = spec.BeaconState.decode_bytes(parts[1][2])
    observed = TARGET.record(TARGET.observation(Context(spec, pre, None, post, {})))
    assert observed["has_slashed_active_validator"] is True
    assert observed["fewer_candidates_than_slots"] == "LT_1"
    assert observed["old_lookahead_contains_slashed"] is False
    assert observed["new_epoch_repeats_old_tail"] is tail_matches


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
@pytest.mark.parametrize(
    ("bucket", "offset"),
    [("LT_FAR", -2), ("LT_1", -1), ("EQ", 0), ("GT_1", 1), ("GT_FAR", 2)],
)
@pytest.mark.parametrize("repeat", [False, True])
def test_candidate_boundaries_and_repetition_match_spec(preset, bucket, offset, repeat):
    selected_spec = spec_targets[preset]["gloas"]
    target = TARGET.for_spec(selected_spec)
    assignment = {"fewer_candidates_than_slots": bucket, "new_proposers_repeat": repeat}
    materializer = ProposerLookaheadMaterializer(selected_spec)
    materializer.rng = Random(124)
    solution = SimpleNamespace(
        **assignment,
        has_slashed_active_validator=True,
        old_lookahead_contains_slashed=False,
        new_epoch_repeats_old_tail=False,
    )
    if offset < 0 and not repeat:
        assert not target.feasible(assignment)
        with pytest.raises(ValueError, match="fewer candidates"):
            materializer.materialize_solution(solution)
        return
    meta, parts = materializer.materialize_solution(solution)
    pre = selected_spec.BeaconState.decode_bytes(parts[0][2])
    post = selected_spec.BeaconState.decode_bytes(parts[1][2])
    observation = target.observation(Context(selected_spec, pre, None, post, {}))
    actual = target.record(observation)
    assert observation["candidate_count"] == int(selected_spec.SLOTS_PER_EPOCH) + offset
    assert all(actual[name] == value for name, value in meta["claimed"].items())
    slots = int(selected_spec.SLOTS_PER_EPOCH)
    assert post.proposer_lookahead[:-slots] == pre.proposer_lookahead[slots:]
    epoch = selected_spec.get_current_epoch(pre) + selected_spec.MIN_SEED_LOOKAHEAD + 1
    assert post.proposer_lookahead[-slots:] == list(
        selected_spec.get_beacon_proposer_indices(pre, epoch)
    )


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_profiles_cover_all_candidate_buckets_and_prune_impossible_repetition(preset):
    target = TARGET.for_spec(spec_targets[preset]["gloas"])
    expected = {"LT_FAR", "LT_1", "EQ", "GT_1", "GT_FAR"}
    for profile in target.profiles.values():
        obligations = profile.run()
        assert {
            dict(o)["fewer_candidates_than_slots"]
            for o in obligations
            if "fewer_candidates_than_slots" in dict(o)
        } == expected
    _, configurations = target._configurations(filtered=True)
    for configuration in configurations:
        assignment = dict(configuration)
        if assignment["fewer_candidates_than_slots"] in ("LT_FAR", "LT_1"):
            assert assignment["new_proposers_repeat"] is True
