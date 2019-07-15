from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.bls import (
    bls_sign,
    only_with_bls,
)
from eth2spec.utils.ssz.ssz_impl import (
    signing_root,
)


@only_with_bls()
def sign_shard_block(spec, state, block, proposer_index=None):
    if proposer_index is None:
        proposer_index = spec.get_shard_block_proposer_index(state, block.shard, block.slot)

    privkey = privkeys[proposer_index]

    block.signature = bls_sign(
        message_hash=signing_root(block),
        privkey=privkey,
        domain=spec.get_domain(
            state,
            spec.DOMAIN_SHARD_PROPOSER,
            spec.compute_epoch_of_shard_slot(block.slot),
        )
    )


def build_empty_shard_block(spec, state, slot, shard, parent_root, signed=False):
    if slot is None:
        slot = state.slot
    block = spec.ShardBlock(
        slot=slot,
        shard=shard,
        beacon_chain_root=state.block_roots[state.slot // spec.SLOTS_PER_HISTORICAL_ROOT],
        parent_root=parent_root,
        signature=b'\x12' * 96,
    )

    if signed:
        sign_shard_block(spec, state, block)

    return block
