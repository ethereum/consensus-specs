from eth2spec.utils.ssz.ssz_impl import signing_root, hash_tree_root

from eth2spec.test.context import with_all_phases, with_state, bls_switch

from eth2spec.test.helpers.block import build_empty_block_for_next_slot


def run_on_block(spec, state, store, block, valid=True):
    if not valid:
        try:
            spec.on_block(store, block)
        except:
            return
        else:
            assert False

    spec.on_block(store, block)
    assert store.blocks[signing_root(block)] == block


@with_all_phases
@with_state
@bls_switch
def test_basic(spec, state):
    state.latest_block_header = spec.BeaconBlockHeader(body_root=hash_tree_root(spec.BeaconBlockBody()))

    # Initialization
    store = spec.get_genesis_store(state)
    time = 100
    spec.on_tick(store, time)
    assert store.time == time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    run_on_block(spec, state, store, block)

    # On receiving a block of next epoch
    store.time = time + spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH
    block = build_empty_block_for_next_slot(spec, state)
    block.slot += spec.SLOTS_PER_EPOCH

    run_on_block(spec, state, store, block)

    # TODO: add tests for justified_root and finalized_root


@with_all_phases
@with_state
@bls_switch
def test_on_block_future_block(spec, state):
    state.latest_block_header = spec.BeaconBlockHeader(body_root=hash_tree_root(spec.BeaconBlockBody()))

    # Initialization
    store = spec.get_genesis_store(state)

    # do not tick time

    # Fail receiving block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    run_on_block(spec, state, store, block, False)


@with_all_phases
@with_state
@bls_switch
def test_on_block_bad_parent_root(spec, state):
    state.latest_block_header = spec.BeaconBlockHeader(body_root=hash_tree_root(spec.BeaconBlockBody()))

    # Initialization
    store = spec.get_genesis_store(state)
    time = 100
    spec.on_tick(store, time)

    # Fail receiving block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    block.parent_root = b'\x45' * 32
    run_on_block(spec, state, store, block, False)


@with_all_phases
@with_state
@bls_switch
def test_on_block_before_finalized(spec, state):
    state.latest_block_header = spec.BeaconBlockHeader(body_root=hash_tree_root(spec.BeaconBlockBody()))

    # Initialization
    store = spec.get_genesis_store(state)
    time = 100
    spec.on_tick(store, time)

    store.finalized_checkpoint = spec.Checkpoint(epoch=store.finalized_checkpoint.epoch + 2, root=store.finalized_checkpoint.root)

    # Fail receiving block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    run_on_block(spec, state, store, block, False)