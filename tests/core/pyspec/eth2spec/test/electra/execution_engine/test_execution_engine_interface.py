from eth2spec.test.context import (
    spec_state_test,
    with_electra_and_later,
)
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
)
from eth2spec.test.helpers.state import next_slot
from eth2spec.utils.ssz.ssz_typing import Bytes32


@with_electra_and_later
@spec_state_test
def test_noop_execution_engine_notify_new_payload(spec, state):
    """
    Test NoopExecutionEngine.notify_new_payload returns True and doesn't modify state
    """
    engine = spec.NoopExecutionEngine()

    # Create payload and capture pre-state
    next_slot(spec, state)
    payload = build_empty_execution_payload(spec, state)
    pre_state = state.copy()

    # Test notify_new_payload
    result = engine.notify_new_payload(
        execution_payload=payload,
        parent_beacon_block_root=state.latest_block_header.parent_root,
        execution_requests_list=[]
    )

    # Verify behavior
    assert result is True
    assert state == pre_state


@with_electra_and_later
@spec_state_test
def test_noop_execution_engine_notify_forkchoice_updated(spec, state):
    """
    Test NoopExecutionEngine.notify_forkchoice_updated returns None and doesn't modify state
    """
    engine = spec.NoopExecutionEngine()
    pre_state = state.copy()

    # Test notify_forkchoice_updated
    result = engine.notify_forkchoice_updated(
        head_block_hash=Bytes32(),
        safe_block_hash=Bytes32(),
        finalized_block_hash=Bytes32(),
        payload_attributes=None
    )

    # Verify behavior
    assert result is None
    assert state == pre_state


@with_electra_and_later
@spec_state_test
def test_noop_execution_engine_get_payload(spec, state):
    """
    Test NoopExecutionEngine.get_payload raises NotImplementedError
    """
    engine = spec.NoopExecutionEngine()
    pre_state = state.copy()

    # Test get_payload raises NotImplementedError
    try:
        engine.get_payload(payload_id=None)
        raise AssertionError("get_payload should raise NotImplementedError")
    except NotImplementedError:
        pass

    # Verify state wasn't modified
    assert state == pre_state


@with_electra_and_later
@spec_state_test
def test_noop_execution_engine_is_valid_block_hash(spec, state):
    """
    Test NoopExecutionEngine.is_valid_block_hash returns True and doesn't modify state
    """
    engine = spec.NoopExecutionEngine()

    # Create payload and capture pre-state
    next_slot(spec, state)
    payload = build_empty_execution_payload(spec, state)
    pre_state = state.copy()

    # Test is_valid_block_hash
    result = engine.is_valid_block_hash(
        execution_payload=payload,
        parent_beacon_block_root=state.latest_block_header.parent_root,
        execution_requests_list=[]
    )

    # Verify behavior
    assert result is True
    assert state == pre_state


@with_electra_and_later
@spec_state_test
def test_noop_execution_engine_is_valid_versioned_hashes(spec, state):
    """
    Test NoopExecutionEngine.is_valid_versioned_hashes returns True and doesn't modify state
    """
    engine = spec.NoopExecutionEngine()
    pre_state = state.copy()

    # Test is_valid_versioned_hashes
    result = engine.is_valid_versioned_hashes(new_payload_request=None)

    # Verify behavior
    assert result is True
    assert state == pre_state


@with_electra_and_later
@spec_state_test
def test_noop_execution_engine_verify_and_notify_new_payload(spec, state):
    """
    Test NoopExecutionEngine.verify_and_notify_new_payload returns True and doesn't modify state
    """
    engine = spec.NoopExecutionEngine()
    pre_state = state.copy()

    # Test verify_and_notify_new_payload
    result = engine.verify_and_notify_new_payload(new_payload_request=None)

    # Verify behavior
    assert result is True
    assert state == pre_state
