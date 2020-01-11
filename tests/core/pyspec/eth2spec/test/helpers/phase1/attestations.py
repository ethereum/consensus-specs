from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils import bls


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
    return bls.Aggregate(signatures)


def get_attestation_signature(spec, beacon_state, shard_state, message_hash, block_epoch, privkey):
    domain = spec.get_domain(beacon_state, spec.DOMAIN_SHARD_ATTESTER, block_epoch)
    signing_root = spec.compute_signing_root(message_hash, domain)
    return bls.Sign(privkey, signing_root)
