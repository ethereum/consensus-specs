from typing import List

from eth2spec.test.context import expect_assertion_error, PHASE0
from eth2spec.test.helpers.state import state_transition_and_sign_block
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

    current_epoch_count = len(state.current_epoch_attestations)
    previous_epoch_count = len(state.previous_epoch_attestations)

    # process attestation
    spec.process_attestation(state, attestation)

    # Make sure the attestation has been processed
    if attestation.data.target.epoch == spec.get_current_epoch(state):
        assert len(state.current_epoch_attestations) == current_epoch_count + 1
    else:
        assert len(state.previous_epoch_attestations) == previous_epoch_count + 1

    # yield post-state
    yield 'post', state


def build_attestation_data(spec, state, slot, index):
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

    return spec.AttestationData(
        slot=slot,
        index=index,
        beacon_block_root=block_root,
        source=spec.Checkpoint(epoch=source_epoch, root=source_root),
        target=spec.Checkpoint(epoch=spec.compute_epoch_at_slot(slot), root=epoch_boundary_root),
    )


def convert_to_valid_on_time_attestation(spec, state, attestation, signed=False):
    shard = spec.get_shard(state, attestation)
    offset_slots = spec.compute_offset_slots(spec.get_latest_slot_for_shard(state, shard), state.slot + 1)
    for offset_slot in offset_slots:
        attestation.custody_bits_blocks.append(
            Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE]([0 for _ in attestation.aggregation_bits])
        )

    if signed:
        sign_attestation(spec, state, attestation)

    return attestation


def get_valid_on_time_attestation(spec, state, slot=None, index=None, signed=False):
    '''
    Construct on-time attestation for next slot
    '''
    if slot is None:
        slot = state.slot
    if index is None:
        index = 0

    return get_valid_attestation(spec, state, slot=slot, index=index, signed=signed, on_time=True)


def get_valid_late_attestation(spec, state, slot=None, index=None, signed=False):
    '''
    Construct on-time attestation for next slot
    '''
    if slot is None:
        slot = state.slot
    if index is None:
        index = 0

    return get_valid_attestation(spec, state, slot=slot, index=index, signed=signed, on_time=False)


def get_valid_attestation(spec, state, slot=None, index=None, empty=False, signed=False, on_time=True):
    if slot is None:
        slot = state.slot
    if index is None:
        index = 0

    attestation_data = build_attestation_data(spec, state, slot, index)

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
    if not empty:
        fill_aggregate_attestation(spec, state, attestation)
    if signed:
        sign_attestation(spec, state, attestation)

    if spec.fork == 'phase1' and on_time:
        attestation = convert_to_valid_on_time_attestation(spec, state, attestation, signed)

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
    if spec.fork == PHASE0:
        participants = indexed_attestation.attesting_indices
        data = indexed_attestation.data
        indexed_attestation.signature = sign_aggregate_attestation(spec, state, data, participants)
    else:
        participants = spec.get_indices_from_committee(
            indexed_attestation.committee,
            indexed_attestation.attestation.aggregation_bits,
        )
        data = indexed_attestation.attestation.data
        indexed_attestation.attestation.signature = sign_aggregate_attestation(spec, state, data, participants)


def sign_on_time_attestation(spec, state, attestation):
    if not any(attestation.custody_bits_blocks):
        sign_attestation(spec, state, attestation)
        return

    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    signatures = []
    for block_index, custody_bits in enumerate(attestation.custody_bits_blocks):
        for participant, abit, cbit in zip(committee, attestation.aggregation_bits, custody_bits):
            if not abit:
                continue
            signatures.append(get_attestation_custody_signature(
                spec,
                state,
                attestation.data,
                block_index,
                cbit,
                privkeys[participant]
            ))

    attestation.signature = bls.Aggregate(signatures)


def get_attestation_custody_signature(spec, state, attestation_data, block_index, bit, privkey):
    domain = spec.get_domain(state, spec.DOMAIN_BEACON_ATTESTER, attestation_data.target.epoch)
    signing_root = spec.compute_signing_root(
        spec.AttestationCustodyBitWrapper(
            attestation_data_root=attestation_data.hash_tree_root(),
            block_index=block_index,
            bit=bit,
        ),
        domain,
    )
    return bls.Sign(privkey, signing_root)


def sign_attestation(spec, state, attestation):
    if spec.fork == 'phase1' and any(attestation.custody_bits_blocks):
        sign_on_time_attestation(spec, state, attestation)
        return

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


def fill_aggregate_attestation(spec, state, attestation, signed=False):
    beacon_committee = spec.get_beacon_committee(
        state,
        attestation.data.slot,
        attestation.data.index,
    )
    for i in range(len(beacon_committee)):
        attestation.aggregation_bits[i] = True

    if signed:
        sign_attestation(spec, state, attestation)


def add_attestations_to_state(spec, state, attestations, slot):
    spec.process_slots(state, slot)
    for attestation in attestations:
        spec.process_attestation(state, attestation)


def next_epoch_with_attestations(spec,
                                 state,
                                 fill_cur_epoch,
                                 fill_prev_epoch):
    assert state.slot % spec.SLOTS_PER_EPOCH == 0

    post_state = state.copy()
    signed_blocks = []
    for _ in range(spec.SLOTS_PER_EPOCH):
        block = build_empty_block_for_next_slot(spec, post_state)
        if fill_cur_epoch and post_state.slot >= spec.MIN_ATTESTATION_INCLUSION_DELAY:
            slot_to_attest = post_state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY + 1
            committees_per_slot = spec.get_committee_count_at_slot(state, slot_to_attest)
            if slot_to_attest >= spec.compute_start_slot_at_epoch(spec.get_current_epoch(post_state)):
                for index in range(committees_per_slot):
                    cur_attestation = get_valid_attestation(spec, post_state, slot_to_attest, index=index, signed=True)
                    block.body.attestations.append(cur_attestation)

        if fill_prev_epoch:
            slot_to_attest = post_state.slot - spec.SLOTS_PER_EPOCH + 1
            committees_per_slot = spec.get_committee_count_at_slot(state, slot_to_attest)
            for index in range(committees_per_slot):
                prev_attestation = get_valid_attestation(
                    spec, post_state, slot_to_attest, index=index, signed=True, on_time=False)
                block.body.attestations.append(prev_attestation)

        signed_block = state_transition_and_sign_block(spec, post_state, block)
        signed_blocks.append(signed_block)

    return state, signed_blocks, post_state
