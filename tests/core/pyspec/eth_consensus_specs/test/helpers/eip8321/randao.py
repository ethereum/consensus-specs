from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.utils import bls

# Tests only ever consume a handful of links, so short chains keep the fixtures
# cheap. The protocol never learns the chain length.
HASH_CHAIN_LENGTH = 8


def compute_chain_secret(spec, validator_index):
    """
    Return a deterministic chain secret for ``validator_index``, so that a test
    can recompute any validator's chain on demand.
    """
    return spec.Bytes32(spec.blake3(b"chain_secret" + int(validator_index).to_bytes(8, "little")))


def compute_hash_chain(spec, validator_index, length=HASH_CHAIN_LENGTH):
    return spec.compute_hash_chain(compute_chain_secret(spec, validator_index), length)


def get_commitment(spec, validator_index, length=HASH_CHAIN_LENGTH):
    """
    Return the tip of the validator's chain, i.e. the value it registers.
    """
    return compute_hash_chain(spec, validator_index, length)[-1]


def get_hash_chain_reveal(spec, state, validator_index):
    """
    Return the preimage of the commitment currently stored for the validator.
    """
    chain = compute_hash_chain(spec, validator_index)
    index = chain.index(state.randao_commitments[validator_index])
    assert index > 0
    return chain[index - 1]


def activate_commitment(spec, state, validator_index, length=HASH_CHAIN_LENGTH):
    """
    Put the validator on the hash-chain path directly, skipping registration.
    """
    commitment = get_commitment(spec, validator_index, length)
    state.randao_commitments[validator_index] = commitment
    return commitment


def sign_randao_commitment_registration(spec, state, registration, privkey):
    domain = spec.compute_domain(
        spec.DOMAIN_RANDAO_COMMITMENT_REGISTRATION,
        genesis_validators_root=state.genesis_validators_root,
    )
    signing_root = spec.compute_signing_root(registration, domain)
    return spec.SignedRandaoCommitmentRegistration(
        message=registration,
        signature=bls.Sign(privkey, signing_root),
    )


def get_signed_registration(spec, state, validator_index=0, commitment=None, privkey=None):
    if commitment is None:
        commitment = get_commitment(spec, validator_index)
    if privkey is None:
        privkey = privkeys[validator_index]

    registration = spec.RandaoCommitmentRegistration(
        validator_index=validator_index,
        commitment=commitment,
    )
    return sign_randao_commitment_registration(spec, state, registration, privkey)
