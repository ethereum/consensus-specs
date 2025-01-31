from eth2spec.test.context import (
    spec_configured_state_test,
    with_bellatrix_and_later,
)
from eth2spec.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth2spec.test.helpers.state import (
    next_epoch,
)


@with_bellatrix_and_later
@spec_configured_state_test({
    'BELLATRIX_FORK_EPOCH': 0
})
def test_get_finalized_execution_payload_hash_equal_to_bellatrix_fork_epoch(spec, state):
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    finalized_block = store.blocks[store.finalized_checkpoint.root]

    finalized_execution_payload_hash = spec.get_finalized_execution_payload_hash(store)

    assert spec.compute_epoch_at_slot(finalized_block.slot) == spec.config.BELLATRIX_FORK_EPOCH
    assert finalized_execution_payload_hash == finalized_block.body.execution_payload.block_hash


@with_bellatrix_and_later
@spec_configured_state_test({
    'BELLATRIX_FORK_EPOCH': 0
})
def test_get_finalized_execution_payload_hash_greater_than_bellatrix_fork_epoch(spec, state):
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    next_epoch(spec, state)
    time = store.time + spec.config.SECONDS_PER_SLOT * (spec.SLOTS_PER_EPOCH + 1)
    spec.on_tick(store, time)

    finalized_block = store.blocks[store.finalized_checkpoint.root]
    # manipulate slot number
    finalized_block.slot = spec.SLOTS_PER_EPOCH

    finalized_execution_payload_hash = spec.get_finalized_execution_payload_hash(store)

    assert spec.compute_epoch_at_slot(finalized_block.slot) > spec.config.BELLATRIX_FORK_EPOCH
    assert finalized_execution_payload_hash == finalized_block.body.execution_payload.block_hash


@with_bellatrix_and_later
@spec_configured_state_test({
    'BELLATRIX_FORK_EPOCH': 1
})
def test_get_finalized_execution_payload_hash_less_than_bellatrix_fork_epoch(spec, state):
    store, _ = get_genesis_forkchoice_store_and_block(spec, state)

    finalized_block = store.blocks[store.finalized_checkpoint.root]

    finalized_execution_payload_hash = spec.get_finalized_execution_payload_hash(store)

    assert spec.compute_epoch_at_slot(finalized_block.slot) < spec.config.BELLATRIX_FORK_EPOCH
    assert finalized_execution_payload_hash == spec.Hash32()
