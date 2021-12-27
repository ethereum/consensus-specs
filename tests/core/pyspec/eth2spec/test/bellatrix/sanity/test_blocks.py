from eth2spec.test.helpers.state import (
    state_transition_and_sign_block
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot
)
from eth2spec.test.context import (
    with_bellatrix_and_later, spec_state_test
)


@with_bellatrix_and_later
@spec_state_test
def test_empty_block_transition_no_tx(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    assert len(block.body.execution_payload.transactions) == 0

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

# TODO: tests with EVM, mock or replacement?


@with_bellatrix_and_later
@spec_state_test
def test_is_execution_enabled_false(spec, state):
    # Set `latest_execution_payload_header` to empty
    state.latest_execution_payload_header = spec.ExecutionPayloadHeader()
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)

    # Set `execution_payload` to empty
    block.body.execution_payload = spec.ExecutionPayload()
    assert len(block.body.execution_payload.transactions) == 0

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state
