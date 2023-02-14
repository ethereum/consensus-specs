from eth2spec.test.helpers.state import (
    state_transition_and_sign_block
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot
)
from eth2spec.test.context import (
    spec_state_test,
    with_deneb_and_later,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)
from eth2spec.test.helpers.sharding import (
    get_sample_opaque_tx,
)


@with_deneb_and_later
@spec_state_test
def test_one_blob(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, _, blob_kzg_commitments = get_sample_opaque_tx(spec)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state


@with_deneb_and_later
@spec_state_test
def test_max_blobs(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, _, blob_kzg_commitments = get_sample_opaque_tx(spec, blob_count=spec.MAX_BLOBS_PER_BLOCK)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state
