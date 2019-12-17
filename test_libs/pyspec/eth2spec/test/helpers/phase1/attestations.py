from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.bls import (
    Aggregate,
    Sign,
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
    return Aggregate(signatures)


def get_attestation_signature(spec, beacon_state, shard_state, message_hash, block_epoch, privkey):
    domain = spec.get_domain(beacon_state, spec.DOMAIN_SHARD_ATTESTER, block_epoch)
    message = spec.compute_domain_wrapper(message_hash, domain)
    return Sign(privkey, message)
