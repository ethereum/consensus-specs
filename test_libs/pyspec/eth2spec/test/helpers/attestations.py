from typing import List

# Access constants from spec pkg reference.
import eth2spec.phase0.spec as spec
from eth2spec.phase0.spec import (
    Attestation,
    AttestationData,
    AttestationDataAndCustodyBit,
    Crosslink,
    get_epoch_start_slot, get_block_root, get_current_epoch, get_previous_epoch, slot_to_epoch,
    get_crosslink_committee, get_domain, IndexedAttestation, get_attesting_indices, BeaconState, get_block_root_at_slot,
    get_epoch_start_shard, get_epoch_committee_count,
    state_transition, process_slots,
)
from eth2spec.test.helpers.bitfields import set_bitfield_bit
from eth2spec.test.helpers.block import build_empty_block_for_next_slot, sign_block
from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.bls import bls_sign, bls_aggregate_signatures
from eth2spec.utils.ssz.ssz_impl import hash_tree_root


def build_attestation_data(state, slot, shard):
    assert state.slot >= slot

    if slot == state.slot:
        block_root = build_empty_block_for_next_slot(state).parent_root
    else:
        block_root = get_block_root_at_slot(state, slot)

    current_epoch_start_slot = get_epoch_start_slot(get_current_epoch(state))
    if slot < current_epoch_start_slot:
        epoch_boundary_root = get_block_root(state, get_previous_epoch(state))
    elif slot == current_epoch_start_slot:
        epoch_boundary_root = block_root
    else:
        epoch_boundary_root = get_block_root(state, get_current_epoch(state))

    if slot < current_epoch_start_slot:
        justified_epoch = state.previous_justified_epoch
        justified_block_root = state.previous_justified_root
    else:
        justified_epoch = state.current_justified_epoch
        justified_block_root = state.current_justified_root

    if slot_to_epoch(slot) == get_current_epoch(state):
        parent_crosslink = state.current_crosslinks[shard]
    else:
        parent_crosslink = state.previous_crosslinks[shard]

    return AttestationData(
        beacon_block_root=block_root,
        source_epoch=justified_epoch,
        source_root=justified_block_root,
        target_epoch=slot_to_epoch(slot),
        target_root=epoch_boundary_root,
        crosslink=Crosslink(
            shard=shard,
            start_epoch=parent_crosslink.end_epoch,
            end_epoch=min(slot_to_epoch(slot), parent_crosslink.end_epoch + spec.MAX_EPOCHS_PER_CROSSLINK),
            data_root=spec.ZERO_HASH,
            parent_root=hash_tree_root(parent_crosslink),
        ),
    )


def get_valid_attestation(state, slot=None, signed=False):
    if slot is None:
        slot = state.slot

    epoch = slot_to_epoch(slot)
    epoch_start_shard = get_epoch_start_shard(state, epoch)
    committees_per_slot = get_epoch_committee_count(state, epoch) // spec.SLOTS_PER_EPOCH
    shard = (epoch_start_shard + committees_per_slot * (slot % spec.SLOTS_PER_EPOCH)) % spec.SHARD_COUNT

    attestation_data = build_attestation_data(state, slot, shard)

    crosslink_committee = get_crosslink_committee(
        state,
        attestation_data.target_epoch,
        attestation_data.crosslink.shard
    )

    committee_size = len(crosslink_committee)
    bitfield_length = (committee_size + 7) // 8
    aggregation_bitfield = b'\x00' * bitfield_length
    custody_bitfield = b'\x00' * bitfield_length
    attestation = Attestation(
        aggregation_bitfield=aggregation_bitfield,
        data=attestation_data,
        custody_bitfield=custody_bitfield,
    )
    fill_aggregate_attestation(state, attestation)
    if signed:
        sign_attestation(state, attestation)
    return attestation


def sign_aggregate_attestation(state: BeaconState, data: AttestationData, participants: List[int]):
    signatures = []
    for validator_index in participants:
        privkey = privkeys[validator_index]
        signatures.append(
            get_attestation_signature(
                state,
                data,
                privkey
            )
        )

    return bls_aggregate_signatures(signatures)


def sign_indexed_attestation(state, indexed_attestation: IndexedAttestation):
    participants = indexed_attestation.custody_bit_0_indices + indexed_attestation.custody_bit_1_indices
    indexed_attestation.signature = sign_aggregate_attestation(state, indexed_attestation.data, participants)


def sign_attestation(state, attestation: Attestation):
    participants = get_attesting_indices(
        state,
        attestation.data,
        attestation.aggregation_bitfield,
    )

    attestation.signature = sign_aggregate_attestation(state, attestation.data, participants)


def get_attestation_signature(state, attestation_data, privkey, custody_bit=0b0):
    message_hash = AttestationDataAndCustodyBit(
        data=attestation_data,
        custody_bit=custody_bit,
    ).hash_tree_root()

    return bls_sign(
        message_hash=message_hash,
        privkey=privkey,
        domain=get_domain(
            state=state,
            domain_type=spec.DOMAIN_ATTESTATION,
            message_epoch=attestation_data.target_epoch,
        )
    )


def fill_aggregate_attestation(state, attestation):
    crosslink_committee = get_crosslink_committee(
        state,
        attestation.data.target_epoch,
        attestation.data.crosslink.shard,
    )
    for i in range(len(crosslink_committee)):
        attestation.aggregation_bitfield = set_bitfield_bit(attestation.aggregation_bitfield, i)


def add_attestation_to_state(state, attestation, slot):
    block = build_empty_block_for_next_slot(state)
    block.slot = slot
    block.body.attestations.append(attestation)
    process_slots(state, block.slot)
    sign_block(state, block)
    state_transition(state, block)
