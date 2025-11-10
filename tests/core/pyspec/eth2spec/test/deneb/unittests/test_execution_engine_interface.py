from eth2spec.test.context import (
    DENEB,
    spec_state_test,
    with_deneb_and_later,
    with_phases,
)
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
)
from eth2spec.test.helpers.state import next_slot


@with_deneb_and_later
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


@with_phases([DENEB])
@spec_state_test
def test_noop_execution_engine_notify_new_payload_deneb(spec, state):
    """
    Test NoopExecutionEngine.notify_new_payload returns True and doesn't modify state
    """
    engine = spec.NoopExecutionEngine()

    next_slot(spec, state)
    payload = build_empty_execution_payload(spec, state)
    result = engine.notify_new_payload(
        execution_payload=payload,
        parent_beacon_block_root=state.latest_block_header.parent_root,
    )

    assert result is True


@with_phases([DENEB])
@spec_state_test
def test_noop_execution_engine_is_valid_block_hash_deneb(spec, state):
    """
    Test NoopExecutionEngine.is_valid_block_hash returns True and doesn't modify state
    """
    engine = spec.NoopExecutionEngine()

    next_slot(spec, state)
    payload = build_empty_execution_payload(spec, state)
    result = engine.is_valid_block_hash(
        execution_payload=payload,
        parent_beacon_block_root=state.latest_block_header.parent_root,
    )

    assert result is True
