from typing import List

from eth2spec.test.helpers.block import build_empty_block_for_next_slot, transition_unsigned_block, \
    build_empty_block
from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils import bls
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


def get_valid_attestation(spec, state, slot=None, index=None, empty=False, signed=False):
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
    # TODO: we should try signing custody bits if spec.fork == 'phase1'
    return bls.Aggregate(signatures)


def sign_indexed_attestation(spec, state, indexed_attestation):
    if spec.fork == 'phase0':
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
    block = build_empty_block(spec, state, slot)
    for attestation in attestations:
        block.body.attestations.append(attestation)
    spec.process_slots(state, block.slot)
    transition_unsigned_block(spec, state, block)
