from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.bls import (
    bls_aggregate_signatures,
    bls_sign,
)


def sign_shard_attestation(spec, shard_state, beacon_state, block, participants):
    signatures = []
    message_hash = block.core.parent_root
    block_epoch = spec.compute_epoch_of_shard_slot(block.core.slot)
    for validator_index in participants:
        privkey = privkeys[validator_index]
        signatures.append(
            get_attestation_signature(
                spec,
                shard_state,
                beacon_state,
                message_hash,
                block_epoch,
                privkey,
            )
        )

    return bls_aggregate_signatures(signatures)


def get_attestation_signature(spec, shard_state, beacon_state, message_hash, block_epoch, privkey):
    return bls_sign(
        message_hash=message_hash,
        privkey=privkey,
        domain=spec.get_domain(
            state=beacon_state,
            domain_type=spec.DOMAIN_SHARD_ATTESTER,
            message_epoch=block_epoch,
        )
    )
