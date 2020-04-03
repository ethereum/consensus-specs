from eth2spec.utils.ssz.ssz_typing import Bitlist
from eth2spec.utils import bls

from eth2spec.test.helpers.keys import privkeys
import eth2spec.test.helpers.attestations as phase0_attestations


def get_valid_on_time_attestation(spec, state, index=None, signed=False):
    '''
    Construct on-time attestation for next slot
    '''
    if index is None:
        index = 0

    attestation = phase0_attestations.get_valid_attestation(spec, state, state.slot, index, False)
    shard = spec.get_shard(state, attestation)
    offset_slots = spec.compute_offset_slots(spec.get_latest_slot_for_shard(state, shard), state.slot + 1)

    for _ in offset_slots:
        attestation.custody_bits_blocks.append(
            Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE]([0 for _ in attestation.aggregation_bits])
        )

    if signed:
        sign_attestation(spec, state, attestation)

    return attestation


def sign_attestation(spec, state, attestation):
    if not any(attestation.custody_bits_blocks):
        phase0_attestations.sign_attestation(spec, state, attestation)
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
            attestation_data.hash_tree_root(),
            block_index,
            bit,
        ),
        domain,
    )
    return bls.Sign(privkey, signing_root)
