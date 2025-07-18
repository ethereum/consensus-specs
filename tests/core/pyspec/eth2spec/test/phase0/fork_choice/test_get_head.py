import random

from eth2spec.test.context import (
    spec_state_test,
    with_all_phases_from_except,
    with_altair_and_later,
    with_presets,
)
from eth2spec.test.helpers.attestations import get_valid_attestation, next_epoch_with_attestations
from eth2spec.test.helpers.block import (
    apply_empty_block,
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.constants import (
    ALTAIR,
    EIP7732,
    MINIMAL,
)
from eth2spec.test.helpers.fork_choice import (
    add_attestation,
    add_attester_slashing,
    add_block,
    apply_next_epoch_with_attestations,
    check_head_against_root,
    get_anchor_root,
    get_formatted_head_output,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    output_head_check,
    tick_and_add_block,
    tick_and_run_on_attestation,
)
from eth2spec.test.helpers.forks import (
    is_post_altair,
    is_post_eip7732,
)
from eth2spec.test.helpers.state import (
    next_epoch,
    next_slots,
    payload_state_transition,
    state_transition_and_sign_block,
)


@with_altair_and_later
@spec_state_test
def test_genesis(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    anchor_root = get_anchor_root(spec, state)
    check_head_against_root(spec, store, anchor_root)

    test_steps.append(
        {
            "checks": {
                "genesis_time": int(store.genesis_time),
                "head": get_formatted_head_output(spec, store),
            }
        }
    )

    yield "steps", test_steps

    if is_post_altair(spec):
        yield (
            "description",
            "meta",
            f"Although it's not phase 0, we may use {spec.fork} spec to start testnets.",
        )


@with_altair_and_later
@spec_state_test
def test_chain_no_attestations(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    anchor_root = get_anchor_root(spec, state)
    check_head_against_root(spec, store, anchor_root)
    output_head_check(spec, store, test_steps)

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block_1 = build_empty_block_for_next_slot(spec, state)
    signed_block_1 = state_transition_and_sign_block(spec, state, block_1)
    yield from tick_and_add_block(spec, store, signed_block_1, test_steps)
    payload_state_transition(spec, store, signed_block_1.message)

    # On receiving a block of next epoch
    block_2 = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)
    yield from tick_and_add_block(spec, store, signed_block_2, test_steps)
    check_head_against_root(spec, store, spec.hash_tree_root(block_2))
    payload_state_transition(spec, store, signed_block_2.message)
    output_head_check(spec, store, test_steps)

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
def test_split_tie_breaker_no_attestations(spec, state):
    test_steps = []
    genesis_state = state.copy()

    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    anchor_root = get_anchor_root(spec, state)
    check_head_against_root(spec, store, anchor_root)
    output_head_check(spec, store, test_steps)

    # Create block at slot 1
    block_1_state = genesis_state.copy()
    block_1 = build_empty_block_for_next_slot(spec, block_1_state)
    signed_block_1 = state_transition_and_sign_block(spec, block_1_state, block_1)

    # Create additional block at slot 1
    block_2_state = genesis_state.copy()
    block_2 = build_empty_block_for_next_slot(spec, block_2_state)
    block_2.body.graffiti = b"\x42" * 32
    signed_block_2 = state_transition_and_sign_block(spec, block_2_state, block_2)

    # Tick time past slot 1 so proposer score boost does not apply
    time = store.genesis_time + (block_2.slot + 1) * spec.config.SECONDS_PER_SLOT
    on_tick_and_append_step(spec, store, time, test_steps)

    yield from add_block(spec, store, signed_block_1, test_steps)
    payload_state_transition(spec, store, signed_block_1.message)
    yield from add_block(spec, store, signed_block_2, test_steps)
    payload_state_transition(spec, store, signed_block_2.message)

    highest_root = max(spec.hash_tree_root(block_1), spec.hash_tree_root(block_2))
    check_head_against_root(spec, store, highest_root)
    output_head_check(spec, store, test_steps)

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
def test_shorter_chain_but_heavier_weight(spec, state):
    test_steps = []
    genesis_state = state.copy()

    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    anchor_root = get_anchor_root(spec, state)
    check_head_against_root(spec, store, anchor_root)
    output_head_check(spec, store, test_steps)

    # build longer tree
    long_state = genesis_state.copy()
    for _ in range(3):
        long_block = build_empty_block_for_next_slot(spec, long_state)
        signed_long_block = state_transition_and_sign_block(spec, long_state, long_block)
        yield from tick_and_add_block(spec, store, signed_long_block, test_steps)
        payload_state_transition(spec, store, signed_long_block.message)

    # build short tree
    short_state = genesis_state.copy()
    short_block = build_empty_block_for_next_slot(spec, short_state)
    short_block.body.graffiti = b"\x42" * 32
    signed_short_block = state_transition_and_sign_block(spec, short_state, short_block)
    yield from tick_and_add_block(spec, store, signed_short_block, test_steps)
    payload_state_transition(spec, store, signed_short_block.message)

    # Since the long chain has higher proposer_score at slot 1, the latest long block is the head
    check_head_against_root(spec, store, spec.hash_tree_root(long_block))

    short_attestation = get_valid_attestation(spec, short_state, short_block.slot, signed=True)
    yield from tick_and_run_on_attestation(spec, store, short_attestation, test_steps)

    check_head_against_root(spec, store, spec.hash_tree_root(short_block))
    output_head_check(spec, store, test_steps)

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_filtered_block_tree(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    anchor_root = get_anchor_root(spec, state)
    check_head_against_root(spec, store, anchor_root)
    output_head_check(spec, store, test_steps)

    # transition state past initial couple of epochs
    next_epoch(spec, state)
    next_epoch(spec, state)
    # fill in attestations for entire epoch, justifying the recent epoch
    prev_state, signed_blocks, state = next_epoch_with_attestations(spec, state, True, False)
    assert state.current_justified_checkpoint.epoch > prev_state.current_justified_checkpoint.epoch

    # tick time forward and add blocks and attestations to store
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    for signed_block in signed_blocks:
        yield from add_block(spec, store, signed_block, test_steps)
        payload_state_transition(spec, store, signed_block.message)

    assert store.justified_checkpoint == state.current_justified_checkpoint

    # the last block in the branch should be the head
    expected_head_root = spec.hash_tree_root(signed_blocks[-1].message)
    check_head_against_root(spec, store, expected_head_root)
    output_head_check(spec, store, test_steps)

    #
    # create branch containing the justified block but not containing enough on
    # chain votes to justify that block
    #

    # build a chain without attestations off of previous justified block
    if is_post_eip7732(spec):
        non_viable_state = store.execution_payload_states[store.justified_checkpoint.root].copy()
    else:
        non_viable_state = store.block_states[store.justified_checkpoint.root].copy()

    # ensure that next wave of votes are for future epoch
    next_epoch(spec, non_viable_state)
    next_epoch(spec, non_viable_state)
    next_epoch(spec, non_viable_state)
    assert spec.get_current_epoch(non_viable_state) > store.justified_checkpoint.epoch

    # create rogue block that will be attested to in this non-viable branch
    rogue_block = build_empty_block_for_next_slot(spec, non_viable_state)
    signed_rogue_block = state_transition_and_sign_block(spec, non_viable_state, rogue_block)

    # create an epoch's worth of attestations for the rogue block
    next_epoch(spec, non_viable_state)
    attestations = []
    for i in range(spec.SLOTS_PER_EPOCH):
        slot = rogue_block.slot + i
        for index in range(
            spec.get_committee_count_per_slot(non_viable_state, spec.compute_epoch_at_slot(slot))
        ):
            attestation = get_valid_attestation(spec, non_viable_state, slot, index, signed=True)
            attestations.append(attestation)

    # tick time forward to be able to include up to the latest attestation
    current_time = (
        attestations[-1].data.slot + 1
    ) * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    # include rogue block and associated attestations in the store
    yield from add_block(spec, store, signed_rogue_block, test_steps)
    payload_state_transition(spec, store, signed_rogue_block.message)

    for attestation in attestations:
        yield from tick_and_run_on_attestation(spec, store, attestation, test_steps)

    # ensure that get_head still returns the head from the previous branch
    check_head_against_root(spec, store, expected_head_root)
    output_head_check(spec, store, test_steps)

    yield "steps", test_steps


# This test is skipped in EIP7732 because the block's slot decides first on weight ties
@with_all_phases_from_except(ALTAIR, [EIP7732])
@spec_state_test
def test_proposer_boost_correct_head(spec, state):
    test_steps = []
    genesis_state = state.copy()

    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    anchor_root = get_anchor_root(spec, state)
    check_head_against_root(spec, store, anchor_root)
    output_head_check(spec, store, test_steps)

    # Build block that serves as head ONLY on timely arrival, and ONLY in that slot
    state_1 = genesis_state.copy()
    next_slots(spec, state_1, 3)
    block_1 = build_empty_block_for_next_slot(spec, state_1)
    signed_block_1 = state_transition_and_sign_block(spec, state_1, block_1)

    # Build block that serves as current head, and remains the head after block_1.slot
    state_2 = genesis_state.copy()
    next_slots(spec, state_2, 2)
    block_2 = build_empty_block_for_next_slot(spec, state_2)
    signed_block_2 = state_transition_and_sign_block(spec, state_2.copy(), block_2)
    rng = random.Random(1001)
    while spec.hash_tree_root(block_1) >= spec.hash_tree_root(block_2):
        block_2.body.graffiti = spec.Bytes32(hex(rng.getrandbits(8 * 32))[2:].zfill(64))
        signed_block_2 = state_transition_and_sign_block(spec, state_2.copy(), block_2)
    assert spec.hash_tree_root(block_1) < spec.hash_tree_root(block_2)

    # Tick to block_1 slot time
    time = store.genesis_time + block_1.slot * spec.config.SECONDS_PER_SLOT
    on_tick_and_append_step(spec, store, time, test_steps)

    # Process block_2
    yield from add_block(spec, store, signed_block_2, test_steps)
    assert store.proposer_boost_root == spec.Root()
    check_head_against_root(spec, store, spec.hash_tree_root(block_2))

    # Process block_1 on timely arrival
    # The head should temporarily change to block_1
    yield from add_block(spec, store, signed_block_1, test_steps)
    assert store.proposer_boost_root == spec.hash_tree_root(block_1)
    check_head_against_root(spec, store, spec.hash_tree_root(block_1))

    # After block_1.slot, the head should revert to block_2
    time = store.genesis_time + (block_1.slot + 1) * spec.config.SECONDS_PER_SLOT
    on_tick_and_append_step(spec, store, time, test_steps)
    assert store.proposer_boost_root == spec.Root()
    check_head_against_root(spec, store, spec.hash_tree_root(block_2))
    output_head_check(spec, store, test_steps)

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
def test_discard_equivocations_on_attester_slashing(spec, state):
    test_steps = []
    genesis_state = state.copy()

    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    anchor_root = get_anchor_root(spec, state)
    check_head_against_root(spec, store, anchor_root)
    output_head_check(spec, store, test_steps)

    # Build block that serves as head before discarding equivocations
    state_1 = genesis_state.copy()
    next_slots(spec, state_1, 2)
    block_1 = build_empty_block_for_next_slot(spec, state_1)
    signed_block_1 = state_transition_and_sign_block(spec, state_1, block_1)

    # Build equivocating attestations to feed to store
    state_eqv = state_1.copy()
    block_eqv = apply_empty_block(spec, state_eqv, state_eqv.slot + 1)
    attestation_eqv = get_valid_attestation(spec, state_eqv, slot=block_eqv.slot, signed=True)

    next_slots(spec, state_1, 1)
    attestation = get_valid_attestation(spec, state_1, slot=block_eqv.slot, signed=True)
    assert spec.is_slashable_attestation_data(attestation.data, attestation_eqv.data)

    indexed_attestation = spec.get_indexed_attestation(state_1, attestation)
    indexed_attestation_eqv = spec.get_indexed_attestation(state_eqv, attestation_eqv)
    attester_slashing = spec.AttesterSlashing(
        attestation_1=indexed_attestation, attestation_2=indexed_attestation_eqv
    )

    # Build block that serves as head after discarding equivocations
    state_2 = genesis_state.copy()
    next_slots(spec, state_2, 3)
    block_2 = build_empty_block_for_next_slot(spec, state_2)
    signed_block_2 = state_transition_and_sign_block(spec, state_2.copy(), block_2)
    rng = random.Random(1001)
    while spec.hash_tree_root(block_1) >= spec.hash_tree_root(block_2):
        block_2.body.graffiti = spec.Bytes32(hex(rng.getrandbits(8 * 32))[2:].zfill(64))
        signed_block_2 = state_transition_and_sign_block(spec, state_2.copy(), block_2)
    assert spec.hash_tree_root(block_1) < spec.hash_tree_root(block_2)

    # Tick to (block_eqv.slot + 2) slot time
    time = store.genesis_time + (block_eqv.slot + 2) * spec.config.SECONDS_PER_SLOT
    on_tick_and_append_step(spec, store, time, test_steps)

    # Process block_1
    yield from add_block(spec, store, signed_block_1, test_steps)
    payload_state_transition(spec, store, signed_block_1.message)
    assert store.proposer_boost_root == spec.Root()
    check_head_against_root(spec, store, spec.hash_tree_root(block_1))

    # Process block_2 head should switch to block_2
    yield from add_block(spec, store, signed_block_2, test_steps)
    payload_state_transition(spec, store, signed_block_2.message)
    assert store.proposer_boost_root == spec.Root()
    check_head_against_root(spec, store, spec.hash_tree_root(block_2))

    # Process attestation
    # The head should change to block_1
    yield from add_attestation(spec, store, attestation, test_steps)
    check_head_against_root(spec, store, spec.hash_tree_root(block_1))

    # Process attester_slashing
    # The head should revert to block_2
    yield from add_attester_slashing(spec, store, attester_slashing, test_steps)
    check_head_against_root(spec, store, spec.hash_tree_root(block_2))
    output_head_check(spec, store, test_steps)

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_discard_equivocations_slashed_validator_censoring(spec, state):
    # Check that the store does not count LMD votes from validators that are slashed in the justified state
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 0
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 0
    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 0

    # We will slash all validators voting at the 2nd slot of epoch 0
    current_slot = spec.get_current_slot(store)
    eqv_slot = current_slot + 1
    eqv_epoch = spec.compute_epoch_at_slot(eqv_slot)
    assert eqv_slot % spec.SLOTS_PER_EPOCH == 1
    assert eqv_epoch == 0
    slashed_validators = []
    comm_count = spec.get_committee_count_per_slot(state, eqv_epoch)
    for comm_index in range(comm_count):
        comm = spec.get_beacon_committee(state, eqv_slot, comm_index)
        slashed_validators += comm
    assert len(slashed_validators) > 0

    # Slash those validators in the state
    for val_index in slashed_validators:
        state.validators[val_index].slashed = True

    # Store this state as the anchor state
    anchor_state = state.copy()
    # Generate an anchor block with correct state root
    anchor_block = spec.BeaconBlock(state_root=anchor_state.hash_tree_root())
    if is_post_eip7732(spec):
        anchor_block.body.signed_execution_payload_header.message.block_hash = (
            anchor_state.latest_block_hash
        )
    yield "anchor_state", anchor_state
    yield "anchor_block", anchor_block

    # Get a new store with the anchor state & anchor block
    store = spec.get_forkchoice_store(anchor_state, anchor_block)
    if is_post_eip7732(spec):
        store.execution_payload_states = store.block_states.copy()

    # Now generate the store checks
    current_time = anchor_state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Create two competing blocks at eqv_slot
    next_slots(spec, state, eqv_slot - state.slot - 1)
    assert state.slot == eqv_slot - 1

    state_1 = state.copy()
    block_1 = build_empty_block_for_next_slot(spec, state_1)
    signed_block_1 = state_transition_and_sign_block(spec, state_1, block_1)

    state_2 = state.copy()
    block_2 = build_empty_block_for_next_slot(spec, state_2)
    block_2.body.graffiti = block_2.body.graffiti = b"\x42" * 32
    signed_block_2 = state_transition_and_sign_block(spec, state_2, block_2)

    assert block_1.slot == block_2.slot == eqv_slot

    # Add both blocks to the store
    yield from tick_and_add_block(spec, store, signed_block_1, test_steps)
    payload_state_transition(spec, store, signed_block_1.message)
    yield from tick_and_add_block(spec, store, signed_block_2, test_steps)
    payload_state_transition(spec, store, signed_block_2.message)

    # Find out which block will win in tie breaking
    if spec.hash_tree_root(block_1) < spec.hash_tree_root(block_2):
        block_low_root = block_1.hash_tree_root()
        block_low_root_post_state = state_1
        block_high_root = block_2.hash_tree_root()
    else:
        block_low_root = block_2.hash_tree_root()
        block_low_root_post_state = state_2
        block_high_root = block_1.hash_tree_root()
    assert block_low_root < block_high_root

    # Tick to next slot so proposer boost does not apply
    current_time = store.genesis_time + (block_1.slot + 1) * spec.config.SECONDS_PER_SLOT
    on_tick_and_append_step(spec, store, current_time, test_steps)

    # Check that block with higher root wins
    check_head_against_root(spec, store, block_high_root)

    # Create attestation for block with lower root
    attestation = get_valid_attestation(
        spec, block_low_root_post_state, slot=eqv_slot, index=0, signed=True
    )
    # Check that all attesting validators were slashed in the anchor state
    att_comm = spec.get_beacon_committee(block_low_root_post_state, eqv_slot, 0)
    for i in att_comm:
        assert anchor_state.validators[i].slashed
    # Add attestation to the store
    yield from add_attestation(spec, store, attestation, test_steps)
    # Check that block with higher root still wins
    check_head_against_root(spec, store, block_high_root)
    output_head_check(spec, store, test_steps)

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_voting_source_within_two_epoch(spec, state):
    """
    Check that the store allows for a head block that has:
    - store.voting_source[block_root].epoch != store.justified_checkpoint.epoch, and
    - store.unrealized_justifications[block_root].epoch >= store.justified_checkpoint.epoch, and
    - store.voting_source[block_root].epoch + 2 >= current_epoch, and
    - store.finalized_checkpoint.root == get_checkpoint_block(store, block_root, store.finalized_checkpoint.epoch)
    """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step(
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert store.finalized_checkpoint.epoch == 2

    # Copy the state to use later
    fork_state = state.copy()

    # Fill epoch 4
    state, store, _ = yield from apply_next_epoch_with_attestations(
        spec, state, store, True, True, test_steps=test_steps
    )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 5
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 4
    assert store.finalized_checkpoint.epoch == 3

    # Create a fork from the earlier saved state
    next_epoch(spec, fork_state)
    assert spec.compute_epoch_at_slot(fork_state.slot) == 5
    _, signed_blocks, fork_state = next_epoch_with_attestations(spec, fork_state, True, True)
    # Only keep the blocks from epoch 5, so discard the last generated block
    signed_blocks = signed_blocks[:-1]
    last_fork_block = signed_blocks[-1].message
    assert spec.compute_epoch_at_slot(last_fork_block.slot) == 5

    # Now add the fork to the store
    for signed_block in signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        payload_state_transition(spec, store, signed_block.message)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 5
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 4
    assert store.finalized_checkpoint.epoch == 3

    # Check that the last block from the fork is the head
    # LMD votes for the competing branch are overwritten so this fork should win
    last_fork_block_root = last_fork_block.hash_tree_root()
    # assert store.voting_source[last_fork_block_root].epoch != store.justified_checkpoint.epoch
    assert (
        store.unrealized_justifications[last_fork_block_root].epoch
        >= store.justified_checkpoint.epoch
    )
    # assert store.voting_source[last_fork_block_root].epoch + 2 >= \
    #     spec.compute_epoch_at_slot(spec.get_current_slot(store))
    assert store.finalized_checkpoint.root == spec.get_checkpoint_block(
        store, last_fork_block_root, store.finalized_checkpoint.epoch
    )
    check_head_against_root(spec, store, last_fork_block_root)

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_voting_source_beyond_two_epoch(spec, state):
    """
    Check that the store doesn't allow for a head block that has:
    - store.voting_source[block_root].epoch != store.justified_checkpoint.epoch, and
    - store.unrealized_justifications[block_root].epoch >= store.justified_checkpoint.epoch, and
    - store.voting_source[block_root].epoch + 2 < current_epoch, and
    - store.finalized_checkpoint.root == get_checkpoint_block(store, block_root, store.finalized_checkpoint.epoch)
    """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step(
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert store.finalized_checkpoint.epoch == 2

    # Copy the state to use later
    fork_state = state.copy()

    # Fill epoch 4 and 5
    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 6
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 5
    assert store.finalized_checkpoint.epoch == 4

    # Create a fork from the earlier saved state
    for _ in range(2):
        next_epoch(spec, fork_state)
    assert spec.compute_epoch_at_slot(fork_state.slot) == 6
    assert fork_state.current_justified_checkpoint.epoch == 3
    _, signed_blocks, fork_state = next_epoch_with_attestations(spec, fork_state, True, True)
    # Only keep the blocks from epoch 6, so discard the last generated block
    signed_blocks = signed_blocks[:-1]
    last_fork_block = signed_blocks[-1].message
    assert spec.compute_epoch_at_slot(last_fork_block.slot) == 6

    # Store the head before adding the fork to the store
    correct_head = spec.get_head(store)
    if is_post_eip7732(spec):
        correct_head = correct_head.root

    # Now add the fork to the store
    for signed_block in signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        payload_state_transition(spec, store, signed_block.message)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 6
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 5
    assert store.finalized_checkpoint.epoch == 4

    last_fork_block_root = last_fork_block.hash_tree_root()
    last_fork_block_state = store.block_states[last_fork_block_root]
    assert last_fork_block_state.current_justified_checkpoint.epoch == 3

    # Check that the head is unchanged
    # assert store.voting_source[last_fork_block_root].epoch != store.justified_checkpoint.epoch
    assert (
        store.unrealized_justifications[last_fork_block_root].epoch
        >= store.justified_checkpoint.epoch
    )
    # assert store.voting_source[last_fork_block_root].epoch + 2 < \
    #     spec.compute_epoch_at_slot(spec.get_current_slot(store))
    assert store.finalized_checkpoint.root == spec.get_checkpoint_block(
        store, last_fork_block_root, store.finalized_checkpoint.epoch
    )
    check_head_against_root(spec, store, correct_head)

    yield "steps", test_steps


"""
Note:
We are unable to generate test vectors that check failure of the correct_finalized condition.
We cannot generate a block that:
- has !correct_finalized, and
- has correct_justified, and
- is a descendant of store.justified_checkpoint.root

The block being a descendant of store.justified_checkpoint.root is necessary because
filter_block_tree descends the tree starting at store.justified_checkpoint.root

@with_altair_and_later
@spec_state_test
def test_incorrect_finalized(spec, state):
    # Check that the store doesn't allow for a head block that has:
    # - store.voting_source[block_root].epoch == store.justified_checkpoint.epoch, and
    # - store.finalized_checkpoint.epoch != GENESIS_EPOCH, and
    # - store.finalized_checkpoint.root != get_checkpoint_block(store, block_root, store.finalized_checkpoint.epoch)
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)

    # Fill epoch 1 to 4
    for _ in range(4):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps)

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 5
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 4
    assert store.finalized_checkpoint.epoch == 3

    # Identify the fork block as the last block in epoch 4
    fork_block_root = state.latest_block_header.parent_root
    fork_block = store.blocks[fork_block_root]
    assert spec.compute_epoch_at_slot(fork_block.slot) == 4
    # Copy the state to use later
    fork_state = store.block_states[fork_block_root].copy()
    assert spec.compute_epoch_at_slot(fork_state.slot) == 4
    assert fork_state.current_justified_checkpoint.epoch == 3
    assert fork_state.finalized_checkpoint.epoch == 2

    # Create a fork from the earlier saved state
    for _ in range(2):
        next_epoch(spec, fork_state)
    assert spec.compute_epoch_at_slot(fork_state.slot) == 6
    assert fork_state.current_justified_checkpoint.epoch == 4
    assert fork_state.finalized_checkpoint.epoch == 3
    # Fill epoch 6
    signed_blocks = []
    _, signed_blocks_1, fork_state = next_epoch_with_attestations(spec, fork_state, True, False)
    signed_blocks += signed_blocks_1
    assert spec.compute_epoch_at_slot(fork_state.slot) == 7
    # Check that epoch 6 is justified in this fork - it will be used as voting source for the tip of this fork
    assert fork_state.current_justified_checkpoint.epoch == 6
    assert fork_state.finalized_checkpoint.epoch == 3
    # Create a chain in epoch 7 that has new justification for epoch 7
    _, signed_blocks_2, fork_state = next_epoch_with_attestations(spec, fork_state, True, False)
    # Only keep the blocks from epoch 7, so discard the last generated block
    signed_blocks_2 = signed_blocks_2[:-1]
    signed_blocks += signed_blocks_2
    last_fork_block = signed_blocks[-1].message
    assert spec.compute_epoch_at_slot(last_fork_block.slot) == 7

    # Now add the fork to the store
    for signed_block in signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        payload_state_transition(spec, store, signed_block.message)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 7
    assert store.justified_checkpoint.epoch == 6
    assert store.finalized_checkpoint.epoch == 3

    # Fill epoch 5 and 6 in the original chain
    for _ in range(2):
        state, store, signed_head_block = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, False, test_steps=test_steps)

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 7
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 6
    assert store.finalized_checkpoint.epoch == 5
    # Store the expected head
    head_root = signed_head_block.message.hash_tree_root()

    # Check that the head is unchanged
    last_fork_block_root = last_fork_block.hash_tree_root()
    assert store.voting_source[last_fork_block_root].epoch == store.justified_checkpoint.epoch
    assert store.finalized_checkpoint.epoch != spec.GENESIS_EPOCH
    finalized_slot = spec.compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    assert store.finalized_checkpoint.root != spec.get_checkpoint_block(
        store,
        block_root,
        store.finalized_checkpoint.epoch
    )
    assert spec.get_head(store) != last_fork_block_root
    check_head_against_root(spec, store, head_root)

    yield 'steps', test_steps
"""
