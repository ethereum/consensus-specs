from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
    build_state_with_incomplete_transition,
    build_state_with_complete_transition,
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
def test_fail_merge_block(spec, state):
    state = build_state_with_complete_transition(spec, state)
    execution_payload = spec.ExecutionPayload()
    body = spec.BeaconBlockBody()
    body.execution_payload = execution_payload
    assert not spec.is_merge_block(state, body)


@with_merge_and_later
@spec_state_test
def test_fail_merge_block_complete_transition(spec, state):
    state = build_state_with_complete_transition(spec, state)
    body = spec.BeaconBlockBody()
    body.execution_payload = build_empty_execution_payload(spec, state)
    assert not spec.is_merge_block(state, body)


@with_merge_and_later
@spec_state_test
def test_fail_merge_block_no_execution_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    body = spec.BeaconBlockBody()
    assert not spec.is_merge_block(state, body)


@with_merge_and_later
@spec_state_test
def test_success_merge_block(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    body = spec.BeaconBlockBody()
    body.execution_payload = build_empty_execution_payload(spec, state)
    assert spec.is_merge_block(state, body)


@with_merge_and_later
@spec_state_test
def test_failed_execution_enabled(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    body = spec.BeaconBlockBody()
    assert not spec.is_execution_enabled(state, body)


@with_merge_and_later
@spec_state_test
def test_success_execution_enabled_before_terminal(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    body = spec.BeaconBlockBody()
    body.execution_payload = build_empty_execution_payload(spec, state)
    assert spec.is_execution_enabled(state, body)


@with_merge_and_later
@spec_state_test
def test_success_execution_enabled_no_execution_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    body = spec.BeaconBlockBody()
    assert spec.is_execution_enabled(state, body)


@with_merge_and_later
@spec_state_test
def test_success_execution_enabled(spec, state):
    state = build_state_with_complete_transition(spec, state)
    body = spec.BeaconBlockBody()
    body.execution_payload = build_empty_execution_payload(spec, state)
    assert spec.is_execution_enabled(state, body)
