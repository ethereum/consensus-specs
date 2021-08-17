from lru import LRU

from typing import List

from eth2spec.test.context import expect_assertion_error, is_post_altair
from eth2spec.test.helpers.state import state_transition_and_sign_block, next_epoch, next_slot
from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils import bls
from eth2spec.utils.ssz.ssz_typing import Bitlist


def run_attestation_processing(spec, state, attestation, valid=True):
    """
    Run ``process_attestation``, yielding:
      - pre-state ('pre')
      - attestation ('attestation')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    # yield pre-state
    yield 'pre', state

    yield 'attestation', attestation

    # If the attestation is invalid, processing is aborted, and there is no post-state.
    if not valid:
        expect_assertion_error(lambda: spec.process_attestation(state, attestation))
        yield 'post', None
        return

    if not is_post_altair(spec):
        current_epoch_count = len(state.current_epoch_attestations)
        previous_epoch_count = len(state.previous_epoch_attestations)

    # process attestation
    spec.process_attestation(state, attestation)

    # Make sure the attestation has been processed
    if not is_post_altair(spec):
        if attestation.data.target.epoch == spec.get_current_epoch(state):
            assert len(state.current_epoch_attestations) == current_epoch_count + 1
        else:
            assert len(state.previous_epoch_attestations) == previous_epoch_count + 1
    else:
        # After accounting reform, there are cases when processing an attestation does not result in any flag updates
        pass

    # yield post-state
    yield 'post', state


def build_attestation_data(spec, state, slot, index, shard=None):
    assert state.slot >= slot

    if slot == state.slot:
        block_root = build_empty_block_for_next_slot(spec, state).parent_root
    else:
        block_root = spec.get_block_root_at_slot(state, slot)

    current_epoch_start_slot = spec.compute_start_slot_at_epoch(spec.get_current_epoch(state))
    if slot < current_epoch_start_slot:
        epoch_boundary_root = spec.get_block_root(state, spec.get_previous_epoch(state))
    elif slot == current_epoch_start_slot:
        epoch_boundary_root = block_root
    else:
        epoch_boundary_root = spec.get_block_root(state, spec.get_current_epoch(state))

    if slot < current_epoch_start_slot:
        source_epoch = state.previous_justified_checkpoint.epoch
        source_root = state.previous_justified_checkpoint.root
    else:
        source_epoch = state.current_justified_checkpoint.epoch
        source_root = state.current_justified_checkpoint.root

    data = spec.AttestationData(
        slot=slot,
        index=index,
        beacon_block_root=block_root,
        source=spec.Checkpoint(epoch=source_epoch, root=source_root),
        target=spec.Checkpoint(epoch=spec.compute_epoch_at_slot(slot), root=epoch_boundary_root),
    )

    # if spec.fork == SHARDING  # TODO: add extra data for shard voting
    return data


def get_valid_attestation(spec,
                          state,
                          slot=None,
                          index=None,
                          filter_participant_set=None,
                          signed=False):
    # If filter_participant_set filters everything, the attestation has 0 participants, and cannot be signed.
    # Thus strictly speaking invalid when no participant is added later.
    if slot is None:
        slot = state.slot
    if index is None:
        index = 0

    attestation_data = build_attestation_data(
        spec, state, slot=slot, index=index
    )

    beacon_committee = spec.get_beacon_committee(
        state,
        attestation_data.slot,
        attestation_data.index,
    )

    committee_size = len(beacon_committee)
    aggregation_bits = Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*([0] * committee_size))
    attestation = spec.Attestation(
        aggregation_bits=aggregation_bits,
        data=attestation_data,
    )
    # fill the attestation with (optionally filtered) participants, and optionally sign it
    fill_aggregate_attestation(spec, state, attestation, signed=signed, filter_participant_set=filter_participant_set)

    return attestation


def sign_aggregate_attestation(spec, state, attestation_data, participants: List[int]):
    signatures = []
    for validator_index in participants:
        privkey = privkeys[validator_index]
        signatures.append(
            get_attestation_signature(
                spec,
                state,
                attestation_data,
                privkey
            )
        )
    return bls.Aggregate(signatures)


def sign_indexed_attestation(spec, state, indexed_attestation):
    participants = indexed_attestation.attesting_indices
    data = indexed_attestation.data
    indexed_attestation.signature = sign_aggregate_attestation(spec, state, data, participants)


def sign_attestation(spec, state, attestation):
    participants = spec.get_attesting_indices(
        state,
        attestation.data,
        attestation.aggregation_bits,
    )

    attestation.signature = sign_aggregate_attestation(spec, state, attestation.data, participants)


def get_attestation_signature(spec, state, attestation_data, privkey):
    domain = spec.get_domain(state, spec.DOMAIN_BEACON_ATTESTER, attestation_data.target.epoch)
    signing_root = spec.compute_signing_root(attestation_data, domain)
    return bls.Sign(privkey, signing_root)


def fill_aggregate_attestation(spec, state, attestation, signed=False, filter_participant_set=None):
    """
     `signed`: Signing is optional.
     `filter_participant_set`: Optional, filters the full committee indices set (default) to a subset that participates
    """
    beacon_committee = spec.get_beacon_committee(
        state,
        attestation.data.slot,
        attestation.data.index,
    )
    # By default, have everyone participate
    participants = set(beacon_committee)
    # But optionally filter the participants to a smaller amount
    if filter_participant_set is not None:
        participants = filter_participant_set(participants)
    for i in range(len(beacon_committee)):
        attestation.aggregation_bits[i] = beacon_committee[i] in participants

    if signed and len(participants) > 0:
        sign_attestation(spec, state, attestation)


def add_attestations_to_state(spec, state, attestations, slot):
    if state.slot < slot:
        spec.process_slots(state, slot)
    for attestation in attestations:
        spec.process_attestation(state, attestation)


def _get_valid_attestation_at_slot(state, spec, slot_to_attest, participation_fn=None):
    committees_per_slot = spec.get_committee_count_per_slot(state, spec.compute_epoch_at_slot(slot_to_attest))
    for index in range(committees_per_slot):
        def participants_filter(comm):
            if participation_fn is None:
                return comm
            else:
                return participation_fn(state.slot, index, comm)
        # if spec.fork == SHARDING:  TODO: add shard data to attestation, include shard headers in block
        yield get_valid_attestation(
            spec,
            state,
            slot_to_attest,
            index=index,
            signed=True,
            filter_participant_set=participants_filter
        )


def next_slots_with_attestations(spec,
                                 state,
                                 slot_count,
                                 fill_cur_epoch,
                                 fill_prev_epoch,
                                 participation_fn=None):
    """
    participation_fn: (slot, committee_index, committee_indices_set) -> participants_indices_set
    """
    post_state = state.copy()
    signed_blocks = []
    for _ in range(slot_count):
        signed_block = state_transition_with_full_block(
            spec,
            post_state,
            fill_cur_epoch,
            fill_prev_epoch,
            participation_fn,
        )
        signed_blocks.append(signed_block)

    return state, signed_blocks, post_state


def next_epoch_with_attestations(spec,
                                 state,
                                 fill_cur_epoch,
                                 fill_prev_epoch,
                                 participation_fn=None):
    assert state.slot % spec.SLOTS_PER_EPOCH == 0

    return next_slots_with_attestations(
        spec,
        state,
        spec.SLOTS_PER_EPOCH,
        fill_cur_epoch,
        fill_prev_epoch,
        participation_fn,
    )


def state_transition_with_full_block(spec, state, fill_cur_epoch, fill_prev_epoch, participation_fn=None):
    """
    Build and apply a block with attestions at the calculated `slot_to_attest` of current epoch and/or previous epoch.
    """
    block = build_empty_block_for_next_slot(spec, state)
    if fill_cur_epoch and state.slot >= spec.MIN_ATTESTATION_INCLUSION_DELAY:
        slot_to_attest = state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY + 1
        if slot_to_attest >= spec.compute_start_slot_at_epoch(spec.get_current_epoch(state)):
            attestations = _get_valid_attestation_at_slot(
                state,
                spec,
                slot_to_attest,
                participation_fn=participation_fn
            )
            for attestation in attestations:
                block.body.attestations.append(attestation)
    if fill_prev_epoch:
        slot_to_attest = state.slot - spec.SLOTS_PER_EPOCH + 1
        attestations = _get_valid_attestation_at_slot(
            state,
            spec,
            slot_to_attest,
            participation_fn=participation_fn
        )
        for attestation in attestations:
            block.body.attestations.append(attestation)

    signed_block = state_transition_and_sign_block(spec, state, block)
    return signed_block


def state_transition_with_full_attestations_block(spec, state, fill_cur_epoch, fill_prev_epoch):
    """
    Build and apply a block with attestions at all valid slots of current epoch and/or previous epoch.
    """
    # Build a block with previous attestations
    block = build_empty_block_for_next_slot(spec, state)
    attestations = []

    if fill_cur_epoch:
        # current epoch
        slots = state.slot % spec.SLOTS_PER_EPOCH
        for slot_offset in range(slots):
            target_slot = state.slot - slot_offset
            attestations += _get_valid_attestation_at_slot(
                state,
                spec,
                target_slot,
            )

    if fill_prev_epoch:
        # attest previous epoch
        slots = spec.SLOTS_PER_EPOCH - state.slot % spec.SLOTS_PER_EPOCH
        for slot_offset in range(1, slots):
            target_slot = state.slot - (state.slot % spec.SLOTS_PER_EPOCH) - slot_offset
            attestations += _get_valid_attestation_at_slot(
                state,
                spec,
                target_slot,
            )

    block.body.attestations = attestations
    signed_block = state_transition_and_sign_block(spec, state, block)
    return signed_block


def prepare_state_with_attestations(spec, state, participation_fn=None):
    """
    Prepare state with attestations according to the ``participation_fn``.
    If no ``participation_fn``, default to "full" -- max committee participation at each slot.

    participation_fn: (slot, committee_index, committee_indices_set) -> participants_indices_set
    """
    # Go to start of next epoch to ensure can have full participation
    next_epoch(spec, state)

    start_slot = state.slot
    start_epoch = spec.get_current_epoch(state)
    next_epoch_start_slot = spec.compute_start_slot_at_epoch(start_epoch + 1)
    attestations = []
    for _ in range(spec.SLOTS_PER_EPOCH + spec.MIN_ATTESTATION_INCLUSION_DELAY):
        # create an attestation for each index in each slot in epoch
        if state.slot < next_epoch_start_slot:
            for committee_index in range(spec.get_committee_count_per_slot(state, spec.get_current_epoch(state))):
                def temp_participants_filter(comm):
                    if participation_fn is None:
                        return comm
                    else:
                        return participation_fn(state.slot, committee_index, comm)
                attestation = get_valid_attestation(spec, state, index=committee_index,
                                                    filter_participant_set=temp_participants_filter, signed=True)
                if any(attestation.aggregation_bits):  # Only if there is at least 1 participant.
                    attestations.append(attestation)
        # fill each created slot in state after inclusion delay
        if state.slot >= start_slot + spec.MIN_ATTESTATION_INCLUSION_DELAY:
            inclusion_slot = state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY
            include_attestations = [att for att in attestations if att.data.slot == inclusion_slot]
            add_attestations_to_state(spec, state, include_attestations, state.slot)
        next_slot(spec, state)

    assert state.slot == next_epoch_start_slot + spec.MIN_ATTESTATION_INCLUSION_DELAY
    if not is_post_altair(spec):
        assert len(state.previous_epoch_attestations) == len(attestations)

    return attestations


_prep_state_cache_dict = LRU(size=10)


def cached_prepare_state_with_attestations(spec, state):
    """
    Cached version of prepare_state_with_attestations,
    but does not return anything, and does not support a participation fn argument
    """
    # If the pre-state is not already known in the LRU, then take it,
    # prepare it with attestations, and put it in the LRU.
    # The input state is likely already cached, so the hash-tree-root does not affect speed.
    key = (spec.fork, state.hash_tree_root())
    global _prep_state_cache_dict
    if key not in _prep_state_cache_dict:
        prepare_state_with_attestations(spec, state)
        _prep_state_cache_dict[key] = state.get_backing()  # cache the tree structure, not the view wrapping it.

    # Put the LRU cache result into the state view, as if we transitioned the original view
    state.set_backing(_prep_state_cache_dict[key])
