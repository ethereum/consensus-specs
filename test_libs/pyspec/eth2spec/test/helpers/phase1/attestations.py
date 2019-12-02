from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.bls import (
    bls_aggregate_signatures,
    bls_sign,
)


def sign_shard_attestation(spec, beacon_state, shard_state, block, participants):
    signatures = []
    message_hash = spec.ShardAttestationData(
        slot=block.slot,
        parent_root=block.parent_root,
    ).hash_tree_root()
    block_epoch = spec.compute_epoch_of_shard_slot(block.slot)
    for validator_index in participants:
        privkey = privkeys[validator_index]
        signatures.append(
            get_attestation_signature(
                spec,
                beacon_state,
                shard_state,
                message_hash,
                block_epoch,
                privkey,
            )
        )

    return bls_aggregate_signatures(signatures)


def get_attestation_signature(spec, beacon_state, shard_state, message_hash, block_epoch, privkey):
    return bls_sign(
        message_hash=message_hash,
        privkey=privkey,
        tag=spec.get_tag(
            state=beacon_state,
            tag_type=spec.TAG_SHARD_ATTESTER,
            message_epoch=block_epoch,
        )
    )
