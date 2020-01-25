from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils import bls
from eth2spec.utils.bls import only_with_bls
from eth2spec.utils.ssz.ssz_impl import (
    hash_tree_root,
)

from .attestations import (
    sign_shard_attestation,
)


@only_with_bls()
def sign_shard_block(spec, beacon_state, shard_state, block, proposer_index=None):
    if proposer_index is None:
        proposer_index = spec.get_shard_proposer_index(beacon_state, shard_state.shard, block.slot)

    privkey = privkeys[proposer_index]
    domain = spec.get_domain(beacon_state, spec.DOMAIN_SHARD_PROPOSER, spec.compute_epoch_of_shard_slot(block.slot))
    signing_root = spec.compute_signing_root(block, domain)
    block.signature = bls.Sign(privkey, signing_root)


def build_empty_shard_block(spec,
                            beacon_state,
                            shard_state,
                            slot,
                            signed=False,
                            full_attestation=False):
    if slot is None:
        slot = shard_state.slot

    previous_beacon_header = beacon_state.latest_block_header.copy()
    if previous_beacon_header.state_root == spec.Bytes32():
        previous_beacon_header.state_root = beacon_state.hash_tree_root()
    beacon_block_root = hash_tree_root(previous_beacon_header)

    previous_block_header = shard_state.latest_block_header.copy()
    if previous_block_header.state_root == spec.Bytes32():
        previous_block_header.state_root = shard_state.hash_tree_root()
    parent_root = hash_tree_root(previous_block_header)

    block = spec.ShardBlock(
        shard=shard_state.shard,
        slot=slot,
        beacon_block_root=beacon_block_root,
        parent_root=parent_root,
        block_size_sum=shard_state.block_size_sum + spec.SHARD_HEADER_SIZE,
    )

    if full_attestation:
        shard_committee = spec.get_shard_committee(beacon_state, shard_state.shard, block.slot)
        block.aggregation_bits = list(
            (True,) * len(shard_committee) +
            (False,) * (spec.MAX_PERIOD_COMMITTEE_SIZE * 2 - len(shard_committee))
        )
    else:
        shard_committee = []

    block.attestations = sign_shard_attestation(
        spec,
        beacon_state,
        shard_state,
        block,
        participants=shard_committee,
    )

    if signed:
        sign_shard_block(spec, beacon_state, shard_state, block)

    return block
