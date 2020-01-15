from eth2spec.test.context import with_all_phases, spec_state_test
from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.attestations import get_valid_attestation, sign_attestation
from eth2spec.test.helpers.state import transition_to, state_transition_and_sign_block


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

    if spec.version == 'phase0':
        sample_index = indexed_attestation.attesting_indices[0]
    else:
        attesting_indices = [
            index for i, index in enumerate(indexed_attestation.committee)
            if attestation.aggregation_bits[i]
        ]
        sample_index = attesting_indices[0]
    assert (
        store.latest_messages[sample_index] ==
        spec.LatestMessage(
            epoch=attestation.data.target.epoch,
            root=attestation.data.beacon_block_root,
        )
    )


@with_all_phases
@spec_state_test
def test_on_attestation_current_epoch(spec, state):
    store = spec.get_forkchoice_store(state)
    spec.on_tick(store, store.time + spec.SECONDS_PER_SLOT * 2)

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # store block in store
    spec.on_block(store, signed_block)

    attestation = get_valid_attestation(spec, state, slot=block.slot, signed=True)
    assert attestation.data.target.epoch == spec.GENESIS_EPOCH
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == spec.GENESIS_EPOCH

    run_on_attestation(spec, state, store, attestation)


@with_all_phases
@spec_state_test
def test_on_attestation_previous_epoch(spec, state):
    store = spec.get_forkchoice_store(state)
    spec.on_tick(store, store.time + spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH)

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # store block in store
    spec.on_block(store, signed_block)

    attestation = get_valid_attestation(spec, state, slot=block.slot, signed=True)
    assert attestation.data.target.epoch == spec.GENESIS_EPOCH
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == spec.GENESIS_EPOCH + 1

    run_on_attestation(spec, state, store, attestation)


@with_all_phases
@spec_state_test
def test_on_attestation_past_epoch(spec, state):
    store = spec.get_forkchoice_store(state)

    # move time forward 2 epochs
    time = store.time + 2 * spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH
    spec.on_tick(store, time)

    # create and store block from 3 epochs ago
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    spec.on_block(store, signed_block)

    # create attestation for past block
    attestation = get_valid_attestation(spec, state, slot=state.slot, signed=True)
    assert attestation.data.target.epoch == spec.GENESIS_EPOCH
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == spec.GENESIS_EPOCH + 2

    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@spec_state_test
def test_on_attestation_mismatched_target_and_slot(spec, state):
    store = spec.get_forkchoice_store(state)
    spec.on_tick(store, store.time + spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH)

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # store block in store
    spec.on_block(store, signed_block)

    attestation = get_valid_attestation(spec, state, slot=block.slot)
    attestation.data.target.epoch += 1
    sign_attestation(spec, state, attestation)

    assert attestation.data.target.epoch == spec.GENESIS_EPOCH + 1
    assert spec.compute_epoch_at_slot(attestation.data.slot) == spec.GENESIS_EPOCH
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == spec.GENESIS_EPOCH + 1

    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@spec_state_test
def test_on_attestation_target_not_in_store(spec, state):
    store = spec.get_forkchoice_store(state)
    time = spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH
    spec.on_tick(store, time)

    # move to immediately before next epoch to make block new target
    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH - 1)

    target_block = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, target_block)

    # do not add target block to store

    attestation = get_valid_attestation(spec, state, slot=target_block.slot, signed=True)
    assert attestation.data.target.root == target_block.hash_tree_root()

    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@spec_state_test
def test_on_attestation_beacon_block_not_in_store(spec, state):
    store = spec.get_forkchoice_store(state)
    time = spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH
    spec.on_tick(store, time)

    # move to immediately before next epoch to make block new target
    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH - 1)

    target_block = build_empty_block_for_next_slot(spec, state)
    signed_target_block = state_transition_and_sign_block(spec, state, target_block)

    # store target in store
    spec.on_block(store, signed_target_block)

    head_block = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, head_block)

    # do not add head block to store

    attestation = get_valid_attestation(spec, state, slot=head_block.slot, signed=True)
    assert attestation.data.target.root == target_block.hash_tree_root()
    assert attestation.data.beacon_block_root == head_block.hash_tree_root()

    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@spec_state_test
def test_on_attestation_future_epoch(spec, state):
    store = spec.get_forkchoice_store(state)
    time = 3 * spec.SECONDS_PER_SLOT
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # store block in store
    spec.on_block(store, signed_block)

    # move state forward but not store
    state.slot = block.slot + spec.SLOTS_PER_EPOCH

    attestation = get_valid_attestation(spec, state, slot=state.slot, signed=True)
    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@spec_state_test
def test_on_attestation_future_block(spec, state):
    store = spec.get_forkchoice_store(state)
    time = spec.SECONDS_PER_SLOT * 5
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    spec.on_block(store, signed_block)

    # attestation for slot immediately prior to the block being attested to
    attestation = get_valid_attestation(spec, state, slot=block.slot - 1, signed=False)
    attestation.data.beacon_block_root = block.hash_tree_root()
    sign_attestation(spec, state, attestation)

    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@spec_state_test
def test_on_attestation_same_slot(spec, state):
    store = spec.get_forkchoice_store(state)
    time = 1 * spec.SECONDS_PER_SLOT
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    spec.on_block(store, signed_block)

    attestation = get_valid_attestation(spec, state, slot=block.slot, signed=True)
    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@spec_state_test
def test_on_attestation_invalid_attestation(spec, state):
    store = spec.get_forkchoice_store(state)
    time = 3 * spec.SECONDS_PER_SLOT
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    spec.on_block(store, signed_block)

    attestation = get_valid_attestation(spec, state, slot=block.slot, signed=True)
    # make invalid by using an invalid committee index
    attestation.data.index = spec.MAX_COMMITTEES_PER_SLOT * spec.SLOTS_PER_EPOCH

    run_on_attestation(spec, state, store, attestation, False)
