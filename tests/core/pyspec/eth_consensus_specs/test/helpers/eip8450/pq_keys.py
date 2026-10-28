from hashlib import sha256

from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.utils import xmss


def get_xmss_secret_key(validator_index, generation=0):
    """
    Return a deterministic leanXMSS seed for ``validator_index``. Each
    ``generation`` gives the validator a different key.
    """
    return sha256(
        b"xmss" + int(validator_index).to_bytes(8, "little") + int(generation).to_bytes(8, "little")
    ).digest()


def get_vrf_root(spec, validator_index, generation=0):
    return spec.VRFRoot(
        sha256(
            b"vrf"
            + int(validator_index).to_bytes(8, "little")
            + int(generation).to_bytes(8, "little")
        ).digest()
    )


def get_pq_public_keys(spec, validator_index, generation=0, vrf_generation=None):
    if vrf_generation is None:
        vrf_generation = generation
    return spec.PQPublicKeys(
        xmss_public_key=xmss.SkToPk(get_xmss_secret_key(validator_index, generation)),
        vrf_root=get_vrf_root(spec, validator_index, vrf_generation),
    )


def get_signed_pq_key_registration(
    spec,
    state,
    validator_index=0,
    generation=0,
    vrf_generation=None,
    public_keys=None,
    xmss_secret_key=None,
    previous_change_epoch=None,
    privkey=None,
    possession=None,
):
    """
    Build a ``SignedPQKeyRegistration`` that is valid against ``state``, unless
    one of the overrides makes it invalid.
    """
    if xmss_secret_key is None:
        xmss_secret_key = get_xmss_secret_key(validator_index, generation)
    if public_keys is None:
        public_keys = get_pq_public_keys(spec, validator_index, generation, vrf_generation)
    if previous_change_epoch is None:
        previous_change_epoch = state.pq_key_change_epochs[validator_index]
    if privkey is None:
        privkey = privkeys[validator_index]
    if possession is None:
        possession = spec.get_pq_possession_proof(
            state, state.validators[validator_index].pubkey, xmss_secret_key
        )

    registration = spec.PQKeyRegistration(
        validator_index=validator_index,
        public_keys=public_keys,
        previous_change_epoch=previous_change_epoch,
    )
    return spec.SignedPQKeyRegistration(
        message=registration,
        possession=possession,
        signature=spec.get_pq_key_registration_signature(state, registration, privkey),
    )


def sign_pq_possession_at(spec, state, validator_pubkey, xmss_secret_key, index):
    """
    Return a signature of the ``PQKeyPossession`` of the key at leaf ``index``.
    """
    xmss_public_key = xmss.SkToPk(xmss_secret_key)
    signing_root = spec.get_pq_possession_signing_root(state, validator_pubkey, xmss_public_key)
    return spec.XMSSSignature(xmss.Sign(xmss_secret_key, signing_root, index))


def register_pq_keys(spec, state, validator_index, generation=0):
    """
    Register keys for the validator directly in ``state``, skipping processing.
    """
    public_keys = get_pq_public_keys(spec, validator_index, generation)
    state.pq_public_keys[validator_index] = public_keys
    state.pq_key_change_epochs[validator_index] = spec.get_current_epoch(state)
    return public_keys
