from typing import List

from eth2spec.test.helpers.block import build_empty_block_for_next_slot, sign_block
from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.bls import bls_sign, bls_aggregate_signatures
from eth2spec.utils.ssz.ssz_impl import hash_tree_root
from eth2spec.utils.ssz.ssz_typing import Bitlist


def build_attestation_data(spec, state, slot, shard):
    assert state.slot >= slot

    if slot == state.slot:
        block_root = build_empty_block_for_next_slot(spec, state).parent_root
    else:
        block_root = spec.get_block_root_at_slot(state, slot)

    current_epoch_start_slot = spec.epoch_start_slot(spec.get_current_epoch(state))
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

    if spec.slot_to_epoch(slot) == spec.get_current_epoch(state):
        parent_crosslink = state.current_crosslinks[shard]
    else:
        parent_crosslink = state.previous_crosslinks[shard]

    return spec.AttestationData(
        beacon_block_root=block_root,
        source=spec.Checkpoint(epoch=source_epoch, root=source_root),
        target=spec.Checkpoint(epoch=spec.slot_to_epoch(slot), root=epoch_boundary_root),
        crosslink=spec.Crosslink(
            shard=shard,
            start_epoch=parent_crosslink.end_epoch,
            end_epoch=min(spec.slot_to_epoch(slot), parent_crosslink.end_epoch + spec.MAX_EPOCHS_PER_CROSSLINK),
            data_root=spec.ZERO_HASH,
            parent_root=hash_tree_root(parent_crosslink),
        ),
    )


def get_valid_attestation(spec, state, slot=None, signed=False):
    if slot is None:
        slot = state.slot

    epoch = spec.slot_to_epoch(slot)
    epoch_start_shard = spec.get_start_shard(state, epoch)
    committees_per_slot = spec.get_committee_count(state, epoch) // spec.SLOTS_PER_EPOCH
    shard = (epoch_start_shard + committees_per_slot * (slot % spec.SLOTS_PER_EPOCH)) % spec.SHARD_COUNT

    attestation_data = build_attestation_data(spec, state, slot, shard)

    crosslink_committee = spec.get_crosslink_committee(
        state,
        attestation_data.target.epoch,
        attestation_data.crosslink.shard,
    )

    committee_size = len(crosslink_committee)
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
            domain_type=spec.DOMAIN_ATTESTATION,
            message_epoch=attestation_data.target.epoch,
        )
    )


def fill_aggregate_attestation(spec, state, attestation):
    crosslink_committee = spec.get_crosslink_committee(
        state,
        attestation.data.target.epoch,
        attestation.data.crosslink.shard,
    )
    for i in range(len(crosslink_committee)):
        attestation.aggregation_bits[i] = True


def add_attestation_to_state(spec, state, attestation, slot):
    block = build_empty_block_for_next_slot(spec, state)
    block.slot = slot
    block.body.attestations.append(attestation)
    spec.process_slots(state, block.slot)
    sign_block(spec, state, block)
    spec.state_transition(state, block)
