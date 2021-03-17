from eth2spec.test.helpers.keys import privkeys
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.utils import bls


def compute_sync_committee_signature(spec, state, slot, privkey, block_root=None):
    domain = spec.get_domain(state, spec.DOMAIN_SYNC_COMMITTEE, spec.compute_epoch_at_slot(slot))
    if block_root is None:
        if slot == state.slot:
            block_root = build_empty_block_for_next_slot(spec, state).parent_root
        else:
            block_root = spec.get_block_root_at_slot(state, slot)
    signing_root = spec.compute_signing_root(block_root, domain)
    return bls.Sign(privkey, signing_root)


def compute_aggregate_sync_committee_signature(spec, state, slot, participants, block_root=None):
    if len(participants) == 0:
        return spec.G2_POINT_AT_INFINITY

    signatures = []
    for validator_index in participants:
        privkey = privkeys[validator_index]
        signatures.append(
            compute_sync_committee_signature(
                spec,
                state,
                slot,
                privkey,
                block_root=block_root,
            )
        )
    return bls.Aggregate(signatures)
