from eth2spec.test.context import with_all_phases, with_state, bls_switch

from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.attestations import get_valid_attestation
from eth2spec.test.helpers.state import next_slot


def run_on_attestation(spec, state, store, attestation, valid=True):
    if not valid:
        try:
            spec.on_attestation(store, attestation)
        except AssertionError:
            return
        else:
            assert False

    indexed_attestation = spec.convert_to_indexed(state, attestation)
    spec.on_attestation(store, attestation)
    assert (
        store.latest_targets[indexed_attestation.custody_bit_0_indices[0]] ==
        spec.Checkpoint(
            epoch=attestation.data.target.epoch,
            root=attestation.data.target.root,
        )
    )


@with_all_phases
@with_state
@bls_switch
def test_on_attestation(spec, state):
    store = spec.get_genesis_store(state)
    time = 100
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state, signed=True)

    # store block in store
    spec.on_block(store, block)

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, slot=block.slot)
    run_on_attestation(spec, state, store, attestation)


@with_all_phases
@with_state
@bls_switch
def test_on_attestation_target_not_in_store(spec, state):
    store = spec.get_genesis_store(state)
    time = 100
    spec.on_tick(store, time)

    # move to next epoch to make block new target
    state.slot += spec.SLOTS_PER_EPOCH

    block = build_empty_block_for_next_slot(spec, state, signed=True)

    # do not add block to store

    next_slot(spec, state)
    attestation = get_valid_attestation(spec, state, slot=block.slot)
    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@with_state
@bls_switch
def test_on_attestation_future_epoch(spec, state):
    store = spec.get_genesis_store(state)
    time = 3 * spec.SECONDS_PER_SLOT
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state, signed=True)

    # store block in store
    spec.on_block(store, block)
    next_slot(spec, state)

    # move state forward but not store
    attestation_slot = block.slot + spec.SLOTS_PER_EPOCH
    state.slot = attestation_slot

    attestation = get_valid_attestation(spec, state, slot=state.slot)
    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@with_state
@bls_switch
def test_on_attestation_same_slot(spec, state):
    store = spec.get_genesis_store(state)
    time = 1 * spec.SECONDS_PER_SLOT
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state, signed=True)

    spec.on_block(store, block)
    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, slot=block.slot)
    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@with_state
@bls_switch
def test_on_attestation_invalid_attestation(spec, state):
    store = spec.get_genesis_store(state)
    time = 3 * spec.SECONDS_PER_SLOT
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state, signed=True)

    spec.on_block(store, block)
    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, slot=block.slot)
    # make attestation invalid
    attestation.custody_bitfield = b'\xf0' + attestation.custody_bitfield[1:]
    run_on_attestation(spec, state, store, attestation, False)
