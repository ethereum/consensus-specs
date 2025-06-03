from eth2spec.test.context import (
    EIP7805,
    spec_state_test,
    with_phases,
)
from eth2spec.test.helpers.execution_payload import build_empty_execution_payload
from eth2spec.test.helpers.state import next_slot


@with_phases([EIP7805])
@spec_state_test
def test_noop_execution_engine_is_valid_block_hash_eip7805(spec, state):
    """
    Test NoopExecutionEngine.is_valid_block_hash returns True and doesn't modify state
    """
    engine = spec.NoopExecutionEngine()

    next_slot(spec, state)
    payload = build_empty_execution_payload(spec, state)
    result = engine.is_valid_block_hash(
        execution_payload=payload,
        parent_beacon_block_root=state.latest_block_header.parent_root,
        execution_requests_list=[],
        inclusion_list_transactions=[],
    )

    assert result is True


@with_phases([EIP7805])
@spec_state_test
def test_noop_execution_engine_notify_new_payload_eip7805(spec, state):
    """
    Test NoopExecutionEngine.notify_new_payload returns True and doesn't modify state
    """
    engine = spec.NoopExecutionEngine()

    next_slot(spec, state)
    payload = build_empty_execution_payload(spec, state)
    result = engine.notify_new_payload(
        execution_payload=payload,
        parent_beacon_block_root=state.latest_block_header.parent_root,
        execution_requests_list=[],
        inclusion_list_transactions=[],
    )

    assert result is True
