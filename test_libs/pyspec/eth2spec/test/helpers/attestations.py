from typing import List

from eth2spec.test.helpers.block import build_empty_block_for_next_slot, sign_block
from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.bls import bls_sign, bls_aggregate_signatures
from eth2spec.utils.ssz.ssz_typing import Bitlist


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


def get_valid_attestation(spec, state, slot=None, index=None, signed=False):
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
    custody_bits = Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*([0] * committee_size))
    attestation = spec.Attestation(
        aggregation_bits=aggregation_bits,
        data=attestation_data,
        custody_bits=custody_bits,
    )
    fill_aggregate_attestation(spec, state, attestation)
    if signed:
        sign_attestation(spec, state, attestation)
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

    return bls_aggregate_signatures(signatures)


def sign_indexed_attestation(spec, state, indexed_attestation):
    participants = indexed_attestation.custody_bit_0_indices + indexed_attestation.custody_bit_1_indices
    indexed_attestation.signature = sign_aggregate_attestation(spec, state, indexed_attestation.data, participants)


def sign_attestation(spec, state, attestation):
    participants = spec.get_attesting_indices(
        state,
        attestation.data,
        attestation.aggregation_bits,
    )

    attestation.signature = sign_aggregate_attestation(spec, state, attestation.data, participants)


def get_attestation_signature(spec, state, attestation_data, privkey, custody_bit=0b0):
    message_hash = spec.AttestationDataAndCustodyBit(
        data=attestation_data,
        custody_bit=custody_bit,
    ).hash_tree_root()

    return bls_sign(
        message_hash=message_hash,
        privkey=privkey,
        domain=spec.get_domain(
            state=state,
            domain_type=spec.DOMAIN_BEACON_ATTESTER,
            message_epoch=attestation_data.target.epoch,
        )
    )


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
    block = build_empty_block_for_next_slot(spec, state)
    block.slot = slot
    for attestation in attestations:
        block.body.attestations.append(attestation)
    spec.process_slots(state, block.slot)
    sign_block(spec, state, block)
    spec.state_transition(state, block)
