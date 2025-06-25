from random import Random

from eth2spec.test.context import (
    spec_state_test,
    with_fulu_and_later,
)
from eth2spec.test.deneb.fork_choice.test_on_block import get_block_with_blob
from eth2spec.test.helpers.fork_choice import (
    BlobData,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block_with_data,
)
from eth2spec.test.helpers.state import state_transition_and_sign_block


@with_fulu_and_later
@spec_state_test
def test_simple_blob_data_peerdas(spec, state):
    """
    Similar to test_simple_blob_data, but in PeerDAS version that is from Fulu onwards.
    It covers code related to the blob sidecars because on_block calls `is_data_available`
    and we are calling `get_data_column_sidecars_from_block` in the test itself.
    """
    rng = Random(1234)

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block, blobs, blob_kzg_proofs = get_block_with_blob(spec, state, rng=rng)
    signed_block = state_transition_and_sign_block(spec, state, block)
    sidecars = spec.get_data_column_sidecars_from_block(
        signed_block, [spec.compute_cells_and_kzg_proofs(blob) for blob in blobs]
    )
    blob_data = BlobData(blobs, blob_kzg_proofs, sidecars)

    yield from tick_and_add_block_with_data(spec, store, signed_block, test_steps, blob_data)

    assert spec.get_head(store) == signed_block.message.hash_tree_root()

    # On receiving a block of next epoch
    block, blobs, blob_kzg_proofs = get_block_with_blob(spec, state, rng=rng)
    signed_block = state_transition_and_sign_block(spec, state, block)
    sidecars = spec.get_data_column_sidecars_from_block(
        signed_block, [spec.compute_cells_and_kzg_proofs(blob) for blob in blobs]
    )
    blob_data = BlobData(blobs, blob_kzg_proofs, sidecars)

    yield from tick_and_add_block_with_data(spec, store, signed_block, test_steps, blob_data)

    assert spec.get_head(store) == signed_block.message.hash_tree_root()

    yield "steps", test_steps
