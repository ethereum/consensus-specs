from eth2spec.utils.ssz.ssz_impl import signing_root, hash_tree_root

from eth2spec.test.context import with_all_phases, with_state, bls_switch

from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.attestations import get_valid_attestation
from eth2spec.test.helpers.state import next_slot


@with_all_phases
@with_state
@bls_switch
def test_basic(spec, state):
    state.latest_block_header = spec.BeaconBlockHeader(body_root=hash_tree_root(spec.BeaconBlockBody()))

    # Initialization
    store = spec.get_genesis_store(state)
    blocks = []
    time = 100
    spec.on_tick(store, time)
    assert store.time == time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    blocks.append(block)
    spec.on_block(store, block)
    assert store.blocks[signing_root(block)] == block

    # On receiving a block of next epoch
    store.time = time + spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH
    block = build_empty_block_for_next_slot(spec, state)
    block.slot += spec.SLOTS_PER_EPOCH
    blocks.append(block)

    spec.on_block(store, block)
    assert store.blocks[signing_root(block)] == block

    # TODO: add tests for justified_root and finalized_root


@with_all_phases
@with_state
@bls_switch
def test_on_attestation(spec, state):
    store = spec.get_genesis_store(state)
    time = 100
    spec.on_tick(store, time)

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, slot=1)
    indexed_attestation = spec.convert_to_indexed(state, attestation)
    spec.on_attestation(store, attestation)
    assert (
        store.latest_targets[indexed_attestation.custody_bit_0_indices[0]] ==
        spec.Target(
            epoch=attestation.data.target_epoch,
            root=attestation.data.target_root,
        )
    )
