from random import Random

from eth2spec.test.context import (
    spec_state_test,
    with_deneb_and_later,
)

from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.fork_choice import (
    BlobData,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block,
    with_blob_data,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.sharding import (
    get_sample_opaque_tx
)


def get_block_with_blob(spec, state, rng=None):
    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, blobs, blob_kzg_commitments, blob_kzg_proofs = get_sample_opaque_tx(spec, blob_count=1, rng=rng)
    block.body.execution_payload.transactions = [opaque_tx]
    # block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    return block, blobs, blob_kzg_proofs


@with_deneb_and_later
@spec_state_test
def test_simple_blob_data(spec, state):
    rng = Random(1234)

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block, blobs, blob_kzg_proofs = get_block_with_blob(spec, state, rng=rng)
    signed_block = state_transition_and_sign_block(spec, state, block)
    blob_data = BlobData(blobs, blob_kzg_proofs)

    def run_func_1():
        yield from tick_and_add_block(spec, store, signed_block, test_steps, blob_data=blob_data)

    yield from with_blob_data(spec, blob_data, run_func_1)

    assert spec.get_head(store) == signed_block.message.hash_tree_root()

    # On receiving a block of next epoch
    store.time = current_time + spec.config.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH
    block, blobs, blob_kzg_proofs = get_block_with_blob(spec, state, rng=rng)
    signed_block = state_transition_and_sign_block(spec, state, block)
    blob_data = BlobData(blobs, blob_kzg_proofs)

    def run_func_2():
        yield from tick_and_add_block(spec, store, signed_block, test_steps, blob_data=blob_data)

    yield from with_blob_data(spec, blob_data, run_func_2)

    assert spec.get_head(store) == signed_block.message.hash_tree_root()

    yield 'steps', test_steps


@with_deneb_and_later
@spec_state_test
def test_invalid_incorrect_proof(spec, state):
    rng = Random(1234)

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block, blobs, blob_kzg_proofs = get_block_with_blob(spec, state, rng=rng)
    signed_block = state_transition_and_sign_block(spec, state, block)
    # Insert incorrect proof
    blob_kzg_proofs = [b'\xc0' + b'\x00' * 47]
    blob_data = BlobData(blobs, blob_kzg_proofs)

    def run_func_1():
        yield from tick_and_add_block(spec, store, signed_block, test_steps, blob_data=blob_data, valid=False)

    yield from with_blob_data(spec, blob_data, run_func_1)

    assert spec.get_head(store) != signed_block.message.hash_tree_root()

    yield 'steps', test_steps
