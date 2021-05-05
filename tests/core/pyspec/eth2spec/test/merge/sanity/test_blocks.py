from eth2spec.test.helpers.state import (
    state_transition_and_sign_block
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot
)
from eth2spec.test.context import (
    with_merge_and_later, spec_state_test
)


@with_merge_and_later
@spec_state_test
def test_empty_block_transition(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    assert len(block.body.execution_payload.transactions) == 0

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

# TODO: tests with EVM, mock or replacement?
