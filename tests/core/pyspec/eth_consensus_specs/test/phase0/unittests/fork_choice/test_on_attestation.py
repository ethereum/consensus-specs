from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_all_phases,
)
from eth_consensus_specs.test.helpers.attestations import get_valid_attestation, sign_attestation
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.fork_choice import get_genesis_forkchoice_store
from eth_consensus_specs.test.helpers.forks import is_post_electra, is_post_gloas
from eth_consensus_specs.test.helpers.state import (
    next_epoch,
    next_slot,
    state_transition_and_sign_block,
    transition_to,
)


def run_on_attestation(spec, state, store, attestation, valid=True):
    if not valid:
        expect_assertion_error(lambda: spec.on_attestation(store, attestation))
        return

    indexed_attestation = spec.get_indexed_attestation(state, attestation)
    spec.on_attestation(store, attestation)

    sample_index = indexed_attestation.attesting_indices[0]
    if is_post_gloas(spec):
        assert attestation.data.index < 2
        latest_message = spec.LatestMessage(
            slot=attestation.data.slot,
            root=attestation.data.beacon_block_root,
            payload_present=attestation.data.index == 1,
        )
    else:
        latest_message = spec.LatestMessage(
            epoch=attestation.data.target.epoch,
            root=attestation.data.beacon_block_root,
        )

    assert store.latest_messages[sample_index] == latest_message


@with_all_phases
@spec_state_test
def test_on_attestation_current_epoch(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    spec.on_tick(store, store.time + spec.config.SECONDS_PER_SLOT * 2)

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
    store = get_genesis_forkchoice_store(spec, state)
    spec.on_tick(store, store.time + spec.config.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH)

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
    store = get_genesis_forkchoice_store(spec, state)

    # move time forward 2 epochs
    time = store.time + 2 * spec.config.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH
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
    store = get_genesis_forkchoice_store(spec, state)
    spec.on_tick(store, store.time + spec.config.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH)

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
def test_on_attestation_inconsistent_target_and_head(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    spec.on_tick(store, store.time + 2 * spec.config.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH)

    # Create chain 1 as empty chain between genesis and start of 1st epoch
    target_state_1 = state.copy()
    next_epoch(spec, target_state_1)

    # Create chain 2 with different block in chain from chain 1 from chain 1 from chain 1 from chain 1
    target_state_2 = state.copy()
    diff_block = build_empty_block_for_next_slot(spec, target_state_2)
    signed_diff_block = state_transition_and_sign_block(spec, target_state_2, diff_block)
    spec.on_block(store, signed_diff_block)
    next_epoch(spec, target_state_2)
    next_slot(spec, target_state_2)

    # Create and store block new head block on target state 1
    head_block = build_empty_block_for_next_slot(spec, target_state_1)
    signed_head_block = state_transition_and_sign_block(spec, target_state_1, head_block)
    spec.on_block(store, signed_head_block)

    # Attest to head of chain 1
    attestation = get_valid_attestation(spec, target_state_1, slot=head_block.slot, signed=False)
    epoch = spec.compute_epoch_at_slot(attestation.data.slot)

    # Set attestation target to be from chain 2
    attestation.data.target = spec.Checkpoint(
        epoch=epoch, root=spec.get_block_root(target_state_2, epoch)
    )
    sign_attestation(spec, state, attestation)

    assert attestation.data.target.epoch == spec.GENESIS_EPOCH + 1
    assert spec.compute_epoch_at_slot(attestation.data.slot) == spec.GENESIS_EPOCH + 1
    assert spec.get_block_root(target_state_1, epoch) != attestation.data.target.root

    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@spec_state_test
def test_on_attestation_target_block_not_in_store(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    time = store.time + spec.config.SECONDS_PER_SLOT * (spec.SLOTS_PER_EPOCH + 1)
    spec.on_tick(store, time)

    # move to immediately before next epoch to make block new target
    next_epoch = spec.get_current_epoch(state) + 1
    transition_to(spec, state, spec.compute_start_slot_at_epoch(next_epoch) - 1)

    target_block = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, target_block)

    # do not add target block to store

    attestation = get_valid_attestation(spec, state, slot=target_block.slot, signed=True)
    assert attestation.data.target.root == target_block.hash_tree_root()

    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@spec_state_test
def test_on_attestation_target_checkpoint_not_in_store(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    time = store.time + spec.config.SECONDS_PER_SLOT * (spec.SLOTS_PER_EPOCH + 1)
    spec.on_tick(store, time)

    # move to immediately before next epoch to make block new target
    next_epoch = spec.get_current_epoch(state) + 1
    transition_to(spec, state, spec.compute_start_slot_at_epoch(next_epoch) - 1)

    target_block = build_empty_block_for_next_slot(spec, state)
    signed_target_block = state_transition_and_sign_block(spec, state, target_block)

    # add target block to store
    spec.on_block(store, signed_target_block)

    # target checkpoint state is not yet in store

    attestation = get_valid_attestation(spec, state, slot=target_block.slot, signed=True)
    assert attestation.data.target.root == target_block.hash_tree_root()

    run_on_attestation(spec, state, store, attestation)


@with_all_phases
@spec_state_test
def test_on_attestation_target_checkpoint_not_in_store_diff_slot(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    time = store.time + spec.config.SECONDS_PER_SLOT * (spec.SLOTS_PER_EPOCH + 1)
    spec.on_tick(store, time)

    # move to two slots before next epoch to make target block one before an empty slot
    next_epoch = spec.get_current_epoch(state) + 1
    transition_to(spec, state, spec.compute_start_slot_at_epoch(next_epoch) - 2)

    target_block = build_empty_block_for_next_slot(spec, state)
    signed_target_block = state_transition_and_sign_block(spec, state, target_block)

    # add target block to store
    spec.on_block(store, signed_target_block)

    # target checkpoint state is not yet in store

    attestation_slot = target_block.slot + 1
    transition_to(spec, state, attestation_slot)
    attestation = get_valid_attestation(spec, state, slot=attestation_slot, signed=True)
    assert attestation.data.target.root == target_block.hash_tree_root()

    run_on_attestation(spec, state, store, attestation)


@with_all_phases
@spec_state_test
def test_on_attestation_beacon_block_not_in_store(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    time = store.time + spec.config.SECONDS_PER_SLOT * (spec.SLOTS_PER_EPOCH + 1)
    spec.on_tick(store, time)

    # move to immediately before next epoch to make block new target
    next_epoch = spec.get_current_epoch(state) + 1
    transition_to(spec, state, spec.compute_start_slot_at_epoch(next_epoch) - 1)

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
    store = get_genesis_forkchoice_store(spec, state)
    time = store.time + 3 * spec.config.SECONDS_PER_SLOT
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # store block in store
    spec.on_block(store, signed_block)

    # move state forward but not store
    next_epoch(spec, state)

    attestation = get_valid_attestation(spec, state, slot=state.slot, signed=True)
    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@spec_state_test
def test_on_attestation_future_block(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    time = store.time + spec.config.SECONDS_PER_SLOT * 5
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
    store = get_genesis_forkchoice_store(spec, state)
    time = store.time + spec.config.SECONDS_PER_SLOT
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    spec.on_block(store, signed_block)

    attestation = get_valid_attestation(spec, state, slot=block.slot, signed=True)
    run_on_attestation(spec, state, store, attestation, False)


@with_all_phases
@spec_state_test
def test_on_attestation_invalid_attestation(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    time = store.time + 3 * spec.config.SECONDS_PER_SLOT
    spec.on_tick(store, time)

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    spec.on_block(store, signed_block)

    attestation = get_valid_attestation(spec, state, slot=block.slot, signed=True)
    # make invalid by using an invalid committee index
    if is_post_electra(spec):
        attestation.committee_bits = spec.Bitvector[spec.MAX_COMMITTEES_PER_SLOT]()
    else:
        attestation.data.index = spec.MAX_COMMITTEES_PER_SLOT * spec.SLOTS_PER_EPOCH

    run_on_attestation(spec, state, store, attestation, False)
