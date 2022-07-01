from eth2spec.test.helpers.state import (
    state_transition_and_sign_block
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot
)
from eth2spec.test.context import (
    spec_state_test,
    with_eip4844_and_later,
)
from eth2spec.test.helpers.sharding import (
    get_sample_opaque_tx,
)


@with_eip4844_and_later
@spec_state_test
def test_simple_blobs(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, _, blob_kzgs = get_sample_opaque_tx(spec)
    block.body.blob_kzgs = blob_kzgs
    block.body.execution_payload.transactions = [opaque_tx]
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state
