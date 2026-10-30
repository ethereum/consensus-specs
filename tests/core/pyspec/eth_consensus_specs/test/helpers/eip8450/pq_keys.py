from hashlib import sha256

from eth_consensus_specs.test.helpers.keys import builder_pubkey_to_privkey, privkeys
from eth_consensus_specs.utils import xmss


def get_xmss_secret_key(index, generation=0):
    """
    Return a deterministic leanXMSS seed for the validator or flagged builder
    ``index``. Each ``generation`` gives the index a different key.
    """
    return sha256(
        b"xmss" + int(index).to_bytes(8, "little") + int(generation).to_bytes(8, "little")
    ).digest()


def get_vrf_root(spec, index, generation=0):
    return spec.VRFRoot(
        sha256(
            b"vrf" + int(index).to_bytes(8, "little") + int(generation).to_bytes(8, "little")
        ).digest()
    )


def get_pq_key_material(spec, index, generation=0, vrf_generation=None):
    """
    Return the keys of the validator or flagged builder ``index``. Builders get a
    zero VRF root.
    """
    if vrf_generation is None:
        vrf_generation = generation
    if spec.is_builder_index(index):
        vrf_root = spec.VRFRoot()
    else:
        vrf_root = get_vrf_root(spec, index, vrf_generation)
    return spec.PQKeyMaterial(
        xmss_public_key=xmss.SkToPk(get_xmss_secret_key(index, generation)),
        vrf_root=vrf_root,
    )


def get_registry_pubkey(spec, state, index):
    """
    Return the BLS public key of the validator or flagged builder ``index``.
    """
    if spec.is_builder_index(index):
        return state.builders[spec.convert_validator_index_to_builder_index(index)].pubkey
    return state.validators[index].pubkey


def get_registry_privkey(spec, state, index):
    if spec.is_builder_index(index):
        return builder_pubkey_to_privkey[get_registry_pubkey(spec, state, index)]
    return privkeys[index]


def get_registry_lists(spec, state, index):
    """
    Return the keys list, the change epochs list, and the position in them of
    the validator or flagged builder ``index``.
    """
    if spec.is_builder_index(index):
        position = spec.convert_validator_index_to_builder_index(index)
        return (
            state.builder_post_quantum_key_material,
            state.builder_post_quantum_key_change_epochs,
            position,
        )
    return state.post_quantum_key_material, state.post_quantum_key_change_epochs, index


def get_pq_entry(spec, state, index):
    """
    Return the stored keys and change epoch of the validator or flagged builder
    ``index``.
    """
    keys, change_epochs, position = get_registry_lists(spec, state, index)
    return keys[position], change_epochs[position]


def is_registered(spec, state, index):
    keys, _ = get_pq_entry(spec, state, index)
    return keys.xmss_public_key != spec.XMSSPublicKey()


def get_possession_signing_root(spec, state, pubkey, xmss_public_key):
    possession = spec.PQKeyPossession(pubkey=pubkey, xmss_public_key=xmss_public_key)
    domain = spec.compute_domain(
        spec.DOMAIN_PQ_KEY_POSSESSION, genesis_validators_root=state.genesis_validators_root
    )
    return spec.compute_signing_root(possession, domain)


def builder_registry_index(spec, builder_index):
    """
    Return the registration index of a builder, with ``BUILDER_INDEX_FLAG`` set.
    """
    return spec.convert_builder_index_to_validator_index(spec.BuilderIndex(builder_index))


def get_signed_pq_key_registration(
    spec,
    state,
    index=0,
    generation=0,
    vrf_generation=None,
    key_material=None,
    xmss_secret_key=None,
    previous_change_epoch=None,
    privkey=None,
    possession=None,
):
    """
    Build a ``SignedPQKeyRegistration`` for the validator or flagged builder
    ``index`` that is valid against ``state``, unless one of the overrides makes
    it invalid.
    """
    if xmss_secret_key is None:
        xmss_secret_key = get_xmss_secret_key(index, generation)
    if key_material is None:
        key_material = get_pq_key_material(spec, index, generation, vrf_generation)
    if previous_change_epoch is None:
        _, previous_change_epoch = get_pq_entry(spec, state, index)
    if privkey is None:
        privkey = get_registry_privkey(spec, state, index)
    if possession is None:
        possession = spec.get_pq_possession_proof(
            state, get_registry_pubkey(spec, state, index), xmss_secret_key
        )

    registration = spec.PQKeyRegistration(
        index=index,
        key_material=key_material,
        previous_change_epoch=previous_change_epoch,
    )
    return spec.SignedPQKeyRegistration(
        message=registration,
        possession=possession,
        signature=spec.get_pq_key_registration_signature(state, registration, privkey),
    )


def sign_pq_possession_at(spec, state, pubkey, xmss_secret_key, index):
    """
    Return a signature of the ``PQKeyPossession`` of the key at leaf ``index``.
    """
    xmss_public_key = xmss.SkToPk(xmss_secret_key)
    signing_root = get_possession_signing_root(spec, state, pubkey, xmss_public_key)
    return spec.XMSSSignature(xmss.Sign(xmss_secret_key, signing_root, index))


def register_pq_keys(spec, state, index, generation=0):
    """
    Register keys for the validator or flagged builder ``index`` directly in
    ``state``, skipping processing.
    """
    key_material = get_pq_key_material(spec, index, generation)
    keys, change_epochs, position = get_registry_lists(spec, state, index)
    keys[position] = key_material
    change_epochs[position] = spec.get_current_epoch(state)
    return key_material


def activate_builders(spec, state):
    """
    Finalize past the genesis epoch, so that builders deposited at genesis are
    active.
    """
    if spec.get_current_epoch(state) < 2:
        state.slot = spec.compute_start_slot_at_epoch(2)
    state.finalized_checkpoint.epoch = max(state.finalized_checkpoint.epoch, 1)
