
from eth2spec.test.context import with_all_phases, spec_state_test
from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.attestations import get_valid_attestation
from eth2spec.test.helpers.state import state_transition_and_sign_block


def run_on_attestation(spec, state, store, attestation, valid=True):
    if not valid:
        try:
            spec.on_attestation(store, attestation)
        except AssertionError:
            return
        else:
            assert False

    indexed_attestation = spec.get_indexed_attestation(state, attestation)
    spec.on_attestation(store, attestation)
    assert (
        store.latest_messages[indexed_attestation.attesting_indices[0]] ==
        spec.LatestMessage(
            epoch=attestation.data.target.epoch,
            root=attestation.data.beacon_block_root,
        )
    )


@with_all_phases
@spec_state_test
def test_on_attestation(spec, state):
    store = spec.get_genesis_store(state)
    time = 100
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, block)

    # store block in store
    spec.on_block(store, block)

    attestation = get_valid_attestation(spec, state, slot=block.slot)
    run_on_attestation(spec, state, store, attestation)


@with_all_phases
@spec_state_test
def test_on_attestation_target_not_in_store(spec, state):
    store = spec.get_genesis_store(state)
    time = 100
    spec.on_tick(store, time)

    # move to next epoch to make block new target
    state.slot += spec.SLOTS_PER_EPOCH

    block = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, block)

    # do not add block to store

    attestation = get_valid_attestation(spec, state, slot=block.slot)
    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@spec_state_test
def test_on_attestation_future_epoch(spec, state):
    store = spec.get_genesis_store(state)
    time = 3 * spec.SECONDS_PER_SLOT
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, block)

    # store block in store
    spec.on_block(store, block)

    # move state forward but not store
    attestation_slot = block.slot + spec.SLOTS_PER_EPOCH
    state.slot = attestation_slot

    attestation = get_valid_attestation(spec, state, slot=state.slot)
    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@spec_state_test
def test_on_attestation_same_slot(spec, state):
    store = spec.get_genesis_store(state)
    time = 1 * spec.SECONDS_PER_SLOT
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, block)

    spec.on_block(store, block)

    attestation = get_valid_attestation(spec, state, slot=block.slot)
    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@spec_state_test
def test_on_attestation_invalid_attestation(spec, state):
    store = spec.get_genesis_store(state)
    time = 3 * spec.SECONDS_PER_SLOT
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, block)

    spec.on_block(store, block)

    attestation = get_valid_attestation(spec, state, slot=block.slot)
    # make invalid by using an invalid committee index
    attestation.data.index = spec.MAX_COMMITTEES_PER_SLOT * spec.SLOTS_PER_EPOCH

    run_on_attestation(spec, state, store, attestation, False)
