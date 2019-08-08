from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.bls import (
    bls_sign,
    only_with_bls,
)
from eth2spec.utils.ssz.ssz_impl import (
    signing_root,
)


@only_with_bls()
def sign_shard_block(spec, state, block, shard, proposer_index=None):
    if proposer_index is None:
        proposer_index = spec.get_shard_block_proposer_index(state, shard, block.core.slot)

    privkey = privkeys[proposer_index]

    block.signatures.proposer_signature = bls_sign(
        message_hash=signing_root(block),
        privkey=privkey,
        domain=spec.get_domain(
            state,
            spec.DOMAIN_SHARD_PROPOSER,
            spec.compute_epoch_of_shard_slot(block.core.slot),
        )
    )


def build_empty_shard_block(spec, state, slot, shard, parent_root, signed=False):
    if slot is None:
        slot = state.slot
    block = spec.ShardBlock(
        core=spec.ExtendedShardBlockCore(
            slot=slot,
            beacon_chain_root=state.block_roots[state.slot % spec.SLOTS_PER_HISTORICAL_ROOT],
            parent_root=parent_root,
        ),
        signatures=spec.ShardBlockSignatures(
            attestation_signature=b'\x12' * 96,
            proposer_signature=b'\x25' * 96,
        )
    )

    if signed:
        sign_shard_block(spec, state, block, shard)

    return block
