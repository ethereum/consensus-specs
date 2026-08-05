from eth_consensus_specs.test.context import (
    ELECTRA,
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.execution_payload import (
    build_empty_execution_payload,
)
from eth_consensus_specs.test.helpers.state import next_slot


@with_phases([ELECTRA])
@spec_state_test
def test_noop_execution_engine_notify_new_payload_electra(spec, state):
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
    )
    assert result is True


@with_phases([ELECTRA])
@spec_state_test
def test_noop_execution_engine_is_valid_block_hash_electra(spec, state):
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
    )

    assert result is True
