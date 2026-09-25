"""Regression checks for slashed validators in the old lookahead."""

from types import SimpleNamespace

import pytest

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context

from .materializer import ProposerLookaheadMaterializer
from .target import TARGET


@pytest.mark.parametrize("tail_matches", [True, False])
def test_slashed_active_validator_is_absent_from_old_lookahead(tail_matches):
    solution = SimpleNamespace(
        fewer_candidates_than_slots=True,
        has_slashed_active_validator=True,
        old_lookahead_contains_slashed=False,
        new_epoch_repeats_old_tail=tail_matches,
    )
    _, parts = ProposerLookaheadMaterializer(spec).materialize_solution(solution)
    pre = spec.BeaconState.decode_bytes(parts[0][2])
    post = spec.BeaconState.decode_bytes(parts[1][2])
    observed = TARGET.record(TARGET.observation(Context(spec, pre, None, post, {})), "predicate")
    assert observed["has_slashed_active_validator"] is True
    assert observed["fewer_candidates_than_slots"] is True
    assert observed["old_lookahead_contains_slashed"] is False
    assert observed["new_epoch_repeats_old_tail"] is tail_matches
