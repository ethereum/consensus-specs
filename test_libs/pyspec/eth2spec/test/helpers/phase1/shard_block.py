from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.bls import (
    bls_sign,
    only_with_bls,
)
from eth2spec.utils.ssz.ssz_impl import (
    signing_root,
)

from .attestations import (
    sign_shard_attestation,
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


def build_empty_shard_block(spec,
                            shard_state,
                            beacon_state,
                            slot,
                            parent_root,
                            signed=False,
                            full_attestation=False):
    if slot is None:
        slot = shard_state.slot

    block = spec.ShardBlock(
        core=spec.ExtendedShardBlockCore(
            slot=slot,
            beacon_chain_root=beacon_state.block_roots[beacon_state.slot % spec.SLOTS_PER_HISTORICAL_ROOT],
            parent_root=parent_root,
        ),
        signatures=spec.ShardBlockSignatures(
            attestation_signature=b'\x00' * 96,
            proposer_signature=b'\x25' * 96,
        )
    )

    # attestation
    if full_attestation:
        attester_committee = spec.get_persistent_committee(beacon_state, shard_state.shard, block.core.slot)
        block.core.attester_bitfield = list(
            (True,) * len(attester_committee) +
            (False,) * (spec.TARGET_PERSISTENT_COMMITTEE_SIZE * 2 - len(attester_committee))
        )
        block.signatures.attestation_signature = sign_shard_attestation(
            spec,
            shard_state,
            beacon_state,
            block,
            participants=attester_committee,
        )
    else:
        block.signatures.attestation_signature = sign_shard_attestation(
            spec,
            shard_state,
            beacon_state,
            block,
            participants=(),
        )

    if signed:
        sign_shard_block(spec, beacon_state, block, shard_state.shard)

    return block
