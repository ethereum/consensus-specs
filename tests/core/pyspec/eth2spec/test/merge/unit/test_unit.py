from eth2spec.utils.ssz.ssz_typing import uint256
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
    build_state_with_incomplete_transition,
    build_state_with_complete_transition,
)
from eth2spec.test.helpers.block import (
    prepare_empty_pow_block
)
from eth2spec.test.context import spec_state_test, with_merge_and_later


@with_merge_and_later
@spec_state_test
def test_fail_merge_complete(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    assert not spec.is_merge_complete(state)


@with_merge_and_later
@spec_state_test
def test_success_merge_complete(spec, state):
    state = build_state_with_complete_transition(spec, state)
    assert spec.is_merge_complete(state)


@with_merge_and_later
@spec_state_test
def test_fail_merge_block_false_false(spec, state):
    state = build_state_with_complete_transition(spec, state)
    execution_payload = spec.ExecutionPayload()
    body = spec.BeaconBlockBody()
    body.execution_payload = execution_payload
    assert not spec.is_merge_block(state, body)


@with_merge_and_later
@spec_state_test
def test_fail_merge_block_false_true(spec, state):
    state = build_state_with_complete_transition(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    body = spec.BeaconBlockBody()
    body.execution_payload = execution_payload
    assert not spec.is_merge_block(state, body)


@with_merge_and_later
@spec_state_test
def test_fail_merge_block_true_false(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    execution_payload = spec.ExecutionPayload()
    body = spec.BeaconBlockBody()
    body.execution_payload = execution_payload
    assert not spec.is_merge_block(state, body)


@with_merge_and_later
@spec_state_test
def test_success_merge_block(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    body = spec.BeaconBlockBody()
    body.execution_payload = execution_payload
    assert spec.is_merge_block(state, body)


@with_merge_and_later
@spec_state_test
def test_fail_execution_enabled_false_false(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    execution_payload = spec.ExecutionPayload()
    body = spec.BeaconBlockBody()
    body.execution_payload = execution_payload
    assert not spec.is_execution_enabled(state, body)


@with_merge_and_later
@spec_state_test
def test_success_execution_enabled_true_false(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    body = spec.BeaconBlockBody()
    body.execution_payload = execution_payload
    assert spec.is_execution_enabled(state, body)


@with_merge_and_later
@spec_state_test
def test_success_execution_enabled_false_true(spec, state):
    state = build_state_with_complete_transition(spec, state)
    execution_payload = spec.ExecutionPayload()
    body = spec.BeaconBlockBody()
    body.execution_payload = execution_payload
    assert spec.is_execution_enabled(state, body)


@with_merge_and_later
@spec_state_test
def test_success_execution_enabled_true_true(spec, state):
    state = build_state_with_complete_transition(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    body = spec.BeaconBlockBody()
    body.execution_payload = execution_payload
    assert spec.is_execution_enabled(state, body)


def compute_terminal_total_difficulty_reference(spec) -> uint256:
    seconds_per_voting_period = spec.EPOCHS_PER_ETH1_VOTING_PERIOD * spec.SLOTS_PER_EPOCH * spec.config.SECONDS_PER_SLOT
    pow_blocks_per_voting_period = seconds_per_voting_period // spec.config.SECONDS_PER_ETH1_BLOCK
    pow_blocks_to_merge = spec.TARGET_SECONDS_TO_MERGE // spec.config.SECONDS_PER_ETH1_BLOCK
    pow_blocks_after_anchor_block = spec.config.ETH1_FOLLOW_DISTANCE + pow_blocks_per_voting_period +\
        pow_blocks_to_merge
    return spec.config.MIN_ANCHOR_POW_BLOCK_DIFFICULTY * uint256(pow_blocks_after_anchor_block)


@with_merge_and_later
@spec_state_test
def test_zero_difficulty(spec, state):
    anchor_pow_block = prepare_empty_pow_block(spec)
    reference_td = compute_terminal_total_difficulty_reference(spec)

    assert spec.compute_terminal_total_difficulty(anchor_pow_block) == reference_td
