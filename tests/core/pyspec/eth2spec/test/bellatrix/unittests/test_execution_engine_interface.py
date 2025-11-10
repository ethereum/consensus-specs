from eth2spec.test.context import (
    BELLATRIX,
    CAPELLA,
    spec_state_test,
    with_bellatrix_and_later,
    with_phases,
)
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
)
from eth2spec.test.helpers.state import next_slot
from eth2spec.utils.ssz.ssz_typing import Bytes32


@with_bellatrix_and_later
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
        payload_attributes=None,
    )

    # Verify behavior
    assert result is None
    assert state == pre_state


@with_bellatrix_and_later
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


@with_bellatrix_and_later
@spec_state_test
def test_noop_execution_engine_verify_and_notify_new_payload(spec, state):
    """
    Test NoopExecutionEngine.verify_and_notify_new_payload returns True and doesn't modify state
    """
    engine = spec.NoopExecutionEngine()
    pre_state = state.copy()

    result = engine.verify_and_notify_new_payload(new_payload_request=None)

    assert result is True
    assert state == pre_state


@with_phases([BELLATRIX, CAPELLA])
@spec_state_test
def test_noop_execution_engine_notify_new_payload_bellatrix_capella(spec, state):
    """
    Test NoopExecutionEngine.notify_new_payload returns True and doesn't modify state
    """
    engine = spec.NoopExecutionEngine()

    next_slot(spec, state)
    payload = build_empty_execution_payload(spec, state)
    result = engine.notify_new_payload(execution_payload=payload)

    assert result is True


@with_phases([BELLATRIX, CAPELLA])
@spec_state_test
def test_noop_execution_engine_is_valid_block_hash_bellatrix_capella(spec, state):
    """
    Test NoopExecutionEngine.is_valid_block_hash returns True and doesn't modify state
    """
    engine = spec.NoopExecutionEngine()

    next_slot(spec, state)
    payload = build_empty_execution_payload(spec, state)
    result = engine.is_valid_block_hash(execution_payload=payload)

    assert result is True
