from eth_utils import encode_hex
from eth2spec.test.context import (
    spec_state_test,
    with_altair_until_eip7732,
)
from eth2spec.test.helpers.attestations import (
    get_valid_attestations_at_slot,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.fork_choice import (
    apply_next_epoch_with_attestations,
    apply_next_slots_with_attestations,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    output_store_checks,
    tick_and_add_block,
    tick_and_run_on_attestation,
)
from eth2spec.test.helpers.state import (
    next_epoch,
    next_slot,
    state_transition_and_sign_block,
)


@with_altair_until_eip7732
@spec_state_test
def test_basic_is_head_root(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
    assert spec.get_head(store) == signed_block.message.hash_tree_root()

    # Proposer of next slot
    head_root = spec.get_head(store)

    # Proposing next slot
    next_slot(spec, state)
    slot = state.slot

    current_time = slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    proposer_head = spec.get_proposer_head(store, head_root, slot)
    assert proposer_head == head_root

    output_store_checks(spec, store, test_steps)
    test_steps.append(
        {
            "checks": {
                "get_proposer_head": encode_hex(proposer_head),
            }
        }
    )

    yield "steps", test_steps


@with_altair_until_eip7732
@spec_state_test
def test_basic_is_parent_root(spec, state):
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
        spec,
        store,
        store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT,
        test_steps,
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 2

    # Make an empty block
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)

    # Fill a slot (parent)
    state, store, signed_parent_block = yield from apply_next_slots_with_attestations(
        spec, state, store, 1, True, True, test_steps
    )

    # Fill a slot with attestations to its parent
    block = build_empty_block_for_next_slot(spec, state)
    parent_block_slot = block.slot - 1
    block.body.attestations = get_valid_attestations_at_slot(
        state,
        spec,
        parent_block_slot,
    )
    signed_block = state_transition_and_sign_block(spec, state, block)

    # Make the head block late
    attesting_cutoff = spec.config.SECONDS_PER_SLOT // spec.INTERVALS_PER_SLOT
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time + attesting_cutoff
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    yield from tick_and_add_block(spec, store, signed_block, test_steps)

    # Check conditions
    head_root = spec.get_head(store)
    head_block = store.blocks[head_root]
    parent_root = head_block.parent_root
    assert parent_root == signed_parent_block.message.hash_tree_root()
    parent_block = store.blocks[parent_root]

    # Proposing next slot
    next_slot(spec, state)
    slot = state.slot

    # Add attestations to the parent block
    attestations = get_valid_attestations_at_slot(
        state,
        spec,
        slot_to_attest=slot - 1,
        beacon_block_root=parent_root,
    )
    for attestation in attestations:
        yield from tick_and_run_on_attestation(spec, store, attestation, test_steps)

    # The conditions in `get_proposer_head`
    assert spec.is_head_late(store, head_root)
    assert spec.is_shuffling_stable(slot)
    assert spec.is_ffg_competitive(store, head_root, parent_root)
    assert spec.is_finalization_ok(store, slot)
    assert spec.is_proposing_on_time(store)

    parent_slot_ok = parent_block.slot + 1 == head_block.slot
    current_time_ok = head_block.slot + 1 == slot
    single_slot_reorg = parent_slot_ok and current_time_ok
    assert single_slot_reorg

    assert spec.is_head_weak(store, head_root)
    assert spec.is_parent_strong(store, parent_root)

    proposer_head = spec.get_proposer_head(store, head_root, state.slot)
    assert proposer_head == parent_root

    output_store_checks(spec, store, test_steps)
    test_steps.append(
        {
            "checks": {
                "get_proposer_head": encode_hex(proposer_head),
            }
        }
    )

    yield "steps", test_steps
