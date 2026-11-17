from eth_consensus_specs.test.context import (
    ForkMeta,
    with_fork_metas,
)
from eth_consensus_specs.test.helpers.attestations import get_valid_attestation
from eth_consensus_specs.test.helpers.block import build_empty_block, sign_block
from eth_consensus_specs.test.helpers.constants import FULU, GLOAS
from eth_consensus_specs.test.helpers.fork_transition import (
    do_fork,
    skip_slots,
    state_transition_across_slots,
)


@with_fork_metas([ForkMeta(pre_fork_name=FULU, post_fork_name=GLOAS, fork_epoch=2)])
def test_transition_skipped_last_pre_fork_slot_misses_head_flag(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    The last pre-fork slot is empty, so its committee votes for the block at the
    slot before it, and the first Gloas block includes that vote at the minimum
    inclusion delay. Pre-fork attesters signal ``data.index = 0``, which Gloas
    reads as a payload vote, and the pre-fork parent counts as available, so the
    vote cannot match. The committee keeps the timely source and target flags but
    misses the timely head flag. This is expected and is not worth a special case
    at the fork boundary.
    """
    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    empty_slot = spec.Uint64(fork_epoch) * spec.SLOTS_PER_EPOCH - 1
    parent_slot = empty_slot - 1

    # Build a block for every slot up to the last pre-fork slot, which is left empty.
    blocks = [
        pre_tag(block)
        for block in state_transition_across_slots(
            spec, state, empty_slot, block_filter=skip_slots(empty_slot)
        )
    ]
    assert state.slot == empty_slot
    assert state.latest_block_header.slot == parent_slot

    state, _ = do_fork(state, spec, post_spec, fork_epoch, with_block=False)
    assert state.slot == empty_slot + 1
    assert state.latest_block_header.slot == parent_slot

    # The empty slot's committee votes for the block at the slot before it.
    attestation = get_valid_attestation(post_spec, state, slot=empty_slot, signed=True)
    assert attestation.data.slot == empty_slot
    assert attestation.data.beacon_block_root == post_spec.get_block_root_at_slot(
        state, parent_slot
    )
    assert attestation.data.index == 0
    assert not post_spec.is_attestation_same_slot(state, attestation.data)
    assert state.slot - attestation.data.slot == post_spec.MIN_ATTESTATION_INCLUSION_DELAY
    attesters = post_spec.get_attesting_indices(state, attestation)
    assert len(attesters) > 0

    # Include the vote in the first Gloas block, which builds on the same parent.
    block = build_empty_block(post_spec, state, slot=state.slot)
    block.body.attestations.append(attestation)
    post_spec.process_block(state, block)
    block.state_root = state.hash_tree_root()
    blocks.append(post_tag(sign_block(post_spec, state, block)))

    assert state.execution_payload_availability[parent_slot % post_spec.SLOTS_PER_HISTORICAL_ROOT]
    for index in attesters:
        flags = state.previous_epoch_participation[index]
        assert post_spec.has_flag(flags, post_spec.TIMELY_SOURCE_FLAG_INDEX)
        assert post_spec.has_flag(flags, post_spec.TIMELY_TARGET_FLAG_INDEX)
        assert not post_spec.has_flag(flags, post_spec.TIMELY_HEAD_FLAG_INDEX)

    yield "blocks", blocks
    yield "post", state


@with_fork_metas([ForkMeta(pre_fork_name=FULU, post_fork_name=GLOAS, fork_epoch=2)])
def test_transition_withheld_first_gloas_payload_gets_head_flag(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    The payload of the first Gloas block is withheld and the slot after it is
    empty, so that slot's committee votes for the first Gloas block with
    ``data.index = 0``. The next block builds on the empty first Gloas block and
    includes that vote at the minimum inclusion delay. The upgrade unsets the
    payload availability of the fork slot, so the vote matches and the committee
    gets the timely head flag, as it would at any other slot.
    """
    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    # Build a block for every slot up to the last pre-fork slot.
    last_pre_fork_slot = spec.Uint64(fork_epoch) * spec.SLOTS_PER_EPOCH - 1
    blocks = [
        pre_tag(block) for block in state_transition_across_slots(spec, state, last_pre_fork_slot)
    ]

    state, _ = do_fork(state, spec, post_spec, fork_epoch, with_block=False)
    fork_slot = state.slot
    fork_slot_index = fork_slot % post_spec.SLOTS_PER_HISTORICAL_ROOT
    assert not state.execution_payload_availability[fork_slot_index]

    # Build the first Gloas block, whose payload is never revealed.
    block = build_empty_block(post_spec, state, slot=fork_slot)
    post_spec.process_block(state, block)
    block.state_root = state.hash_tree_root()
    blocks.append(post_tag(sign_block(post_spec, state, block)))

    # The empty slot's committee votes for the first Gloas block.
    empty_slot = fork_slot + 1
    post_spec.process_slots(state, empty_slot + 1)
    attestation = get_valid_attestation(post_spec, state, slot=empty_slot, signed=True)
    assert attestation.data.beacon_block_root == post_spec.get_block_root_at_slot(state, fork_slot)
    assert attestation.data.index == 0
    assert not post_spec.is_attestation_same_slot(state, attestation.data)
    assert state.slot - attestation.data.slot == post_spec.MIN_ATTESTATION_INCLUSION_DELAY
    attesters = post_spec.get_attesting_indices(state, attestation)
    assert len(attesters) > 0

    # Include the vote in a block that builds on the empty first Gloas block.
    block = build_empty_block(post_spec, state, slot=state.slot)
    bid = block.body.signed_execution_payload_bid.message
    assert bid.parent_block_hash != state.latest_execution_payload_bid.block_hash
    block.body.attestations.append(attestation)
    post_spec.process_block(state, block)
    block.state_root = state.hash_tree_root()
    blocks.append(post_tag(sign_block(post_spec, state, block)))

    assert not state.execution_payload_availability[fork_slot_index]
    for index in attesters:
        flags = state.current_epoch_participation[index]
        assert post_spec.has_flag(flags, post_spec.TIMELY_SOURCE_FLAG_INDEX)
        assert post_spec.has_flag(flags, post_spec.TIMELY_TARGET_FLAG_INDEX)
        assert post_spec.has_flag(flags, post_spec.TIMELY_HEAD_FLAG_INDEX)

    yield "blocks", blocks
    yield "post", state
