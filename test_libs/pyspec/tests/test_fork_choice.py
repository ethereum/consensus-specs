
import eth2spec.phase0.spec as spec
from eth2spec.utils.minimal_ssz import (
    signing_root,
)

from tests.helpers import (
    build_empty_block_for_next_slot,
    get_valid_attestation,
    next_slot,
)


def test_basic(state):
    # Initialization
    store = spec.get_genesis_store(state)
    time = 100
    spec.on_tick(store, time)
    assert store.time == time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(state)
    spec.on_block(store, block)
    assert store.blocks[signing_root(block)] == block

    # On receiving a block of next epoch
    store.time = time + spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH
    block = build_empty_block_for_next_slot(state)
    block.slot += spec.SLOTS_PER_EPOCH

    spec.on_block(store, block)
    assert store.blocks[signing_root(block)] == block

    # TODO: add tests for justified_root and finalized_root


def test_on_attestation(state):
    store = spec.get_genesis_store(state)
    time = 100
    spec.on_tick(store, time)

    next_slot(state)

    attestation = get_valid_attestation(state, slot=1)
    indexed_attestation = spec.convert_to_indexed(state, attestation)
    spec.on_attestation(store, attestation)
    assert (
        store.latest_targets[indexed_attestation.custody_bit_0_indices[0]] ==
        spec.Target(attestation.data.target_epoch, attestation.data.target_root)
    )
