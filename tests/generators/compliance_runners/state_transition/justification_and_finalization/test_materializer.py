from random import Random
from types import SimpleNamespace

import pytest

from eth_consensus_specs.gloas import minimal as spec
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.phase0.epoch_processing.test_process_justification_and_finalization import (
    finalize_on_12,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import score
from tests.generators.compliance_runners.state_transition.evaluation.invariant_scan import (
    entry_condition_violations,
)
from tests.generators.compliance_runners.state_transition.provider import load_provider

from .materializer import MATERIALIZER


def test_recover_current_only_rule_4_from_reference_case():
    state = create_genesis_state(
        spec, [spec.MAX_EFFECTIVE_BALANCE] * 64, spec.MAX_EFFECTIVE_BALANCE
    )
    # Recreate the 12_ok_support vector without depending on downloaded fixtures.
    vector = finalize_on_12(spec, state, 3, sufficient_support=True, messed_up_target=False)
    states = {name: value.copy() for name, value in vector if name in ("pre", "post")}
    pre, post = states["pre"], states["post"]
    assert post.finalized_checkpoint == pre.current_justified_checkpoint
    assert post.finalized_checkpoint != pre.finalized_checkpoint

    provider = load_provider("justification_and_finalization", spec=spec)
    record = provider.recover(pre, None)
    assert record == {
        "past_initial_epochs": True,
        "previous_epoch_supermajority": False,
        "current_epoch_supermajority": True,
        "finalization_path": 4,
    }
    target = provider.TARGET.for_spec(spec)
    assert not score(target, [record], target.profiles["max"]).unexpected


def _materialize(**record):
    materializer = MATERIALIZER(spec)
    materializer.rng = Random(0)
    _, parts = materializer.materialize_solution(SimpleNamespace(**record))
    return {name: spec.BeaconState.decode_bytes(data) for name, _, data in parts}


def test_max_vectors_start_after_slot_processing():
    provider = load_provider("justification_and_finalization", spec=spec)
    profile = provider.TARGET.for_spec(spec).profiles["max"]
    for record in profile.generation_obligations():
        pre = _materialize(**dict(record))["pre"]
        assert not list(entry_condition_violations(spec, pre, "epoch_processing")), record


def test_early_epoch_guard_preserves_state_despite_current_support():
    states = _materialize(past_initial_epochs=False)
    pre = states["pre"]
    indices = spec.get_unslashed_participating_indices(
        pre, spec.TIMELY_TARGET_FLAG_INDEX, spec.get_current_epoch(pre)
    )
    assert 3 * spec.get_total_balance(pre, indices) >= 2 * spec.get_total_active_balance(pre)
    assert states["post"] == pre


def test_previous_only_justification_changes_checkpoint_root():
    states = _materialize(
        past_initial_epochs=True,
        previous_epoch_supermajority=True,
        current_epoch_supermajority=False,
        finalization_path=0,
    )
    pre, post = states["pre"], states["post"]
    previous_epoch = spec.get_previous_epoch(pre)
    expected_root = spec.get_block_root(pre, previous_epoch)
    assert pre.current_justified_checkpoint.root != expected_root
    assert post.current_justified_checkpoint == spec.Checkpoint(
        epoch=previous_epoch, root=expected_root
    )


@pytest.mark.parametrize("rule", [1, 2])
def test_fresh_support_vectors_require_previous_epoch_votes(rule):
    states = _materialize(
        past_initial_epochs=True,
        previous_epoch_supermajority=True,
        current_epoch_supermajority=False,
        finalization_path=rule,
    )
    pre, post = states["pre"], states["post"]
    without_support = pre.copy()
    for i in range(len(without_support.previous_epoch_participation)):
        without_support.previous_epoch_participation[i] = spec.ParticipationFlags(0)
    spec.process_justification_and_finalization(without_support)

    assert without_support.finalized_checkpoint == pre.finalized_checkpoint
    assert without_support.current_justified_checkpoint == pre.current_justified_checkpoint
    assert post.finalized_checkpoint == pre.previous_justified_checkpoint
    assert post.finalized_checkpoint != pre.finalized_checkpoint
    assert post.current_justified_checkpoint.epoch == spec.get_previous_epoch(pre)
    assert post.current_justified_checkpoint.epoch > pre.current_justified_checkpoint.epoch


@pytest.mark.parametrize("rule", [1, 2])
def test_carried_justification_after_a_supporter_is_slashed(rule):
    provider = load_provider("justification_and_finalization", spec=spec)
    target = provider.TARGET.for_spec(spec)
    profile = target.profiles["max"]
    cases = [
        record
        for record in map(dict, profile.generation_obligations())
        if record.get("finalization_path") == rule
    ]
    assert {record["previous_epoch_supermajority"] for record in cases} == {False, True}

    carried = next(record for record in cases if not record["previous_epoch_supermajority"])
    pre = _materialize(**carried)["pre"]
    flag = spec.TIMELY_TARGET_FLAG_INDEX
    supporters = [
        i for i, flags in enumerate(pre.previous_epoch_participation) if spec.has_flag(flags, flag)
    ]
    assert len(supporters) == 43
    assert sum(bool(pre.validators[i].slashed) for i in supporters) == 1
    recovered = provider.recover(pre, None)
    assert recovered == carried
    assert not score(target, [recovered], profile).unexpected

    pre.justification_bits[0] = False
    assert provider.recover(pre, None)["finalization_path"] == 0
