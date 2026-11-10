from eth_consensus_specs.test.helpers.keys import get_vrf_root, privkeys, xmss_pubkeys
from eth_consensus_specs.utils import bls, xmss


def preregistration_withdrawal_credentials(spec, address_byte=b"\x59"):
    """Create eth1 withdrawal credentials from a repeated address byte."""
    return spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + address_byte * 20


def build_preregistration_request(
    spec, state, pubkey, privkey, withdrawal_credentials, valid_signature=True
):
    """
    Build a ``PreregistrationRequest`` signed over the ``ValidatorPreregistration``
    message with the fork-agnostic ``DOMAIN_PREREGISTRATION`` domain.
    """
    preregistration = spec.ValidatorPreregistration(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
    )
    domain = spec.compute_domain(
        spec.DOMAIN_PREREGISTRATION,
        genesis_validators_root=state.genesis_validators_root,
    )
    signing_root = spec.compute_signing_root(preregistration, domain)
    signing_privkey = privkey if valid_signature else privkey + 1
    return spec.PreregistrationRequest(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        signature=bls.Sign(signing_privkey, signing_root),
    )


def build_pq_preregistration_request(spec, state, index, withdrawal_credentials, vrf_root=None):
    """
    Build a ``PreregistrationRequest`` for the XMSS key at ``index``, binding it
    to ``withdrawal_credentials`` and ``vrf_root``, by default the key's own VRF
    root.
    """
    if vrf_root is None:
        vrf_root = get_vrf_root(index)
    preregistration = spec.ValidatorPreregistration(
        pubkey=xmss_pubkeys[index],
        withdrawal_credentials=withdrawal_credentials,
        vrf_root=vrf_root,
    )
    domain = spec.compute_domain(
        spec.DOMAIN_PREREGISTRATION,
        genesis_validators_root=state.genesis_validators_root,
    )
    signing_root = spec.compute_signing_root(preregistration, domain)
    return spec.PreregistrationRequest(
        pubkey=xmss_pubkeys[index],
        withdrawal_credentials=withdrawal_credentials,
        vrf_root=vrf_root,
        signature=xmss.Sign(privkeys[index], spec.RESERVED_LEAF_PREREGISTRATION, signing_root),
    )


def build_pq_stored_preregistration(spec, index, expiry_slot, withdrawal_credentials=None):
    """
    Build a ``StoredPreregistration`` for the XMSS key at ``index`` that expires
    at ``expiry_slot``.
    """
    if withdrawal_credentials is None:
        withdrawal_credentials = preregistration_withdrawal_credentials(spec)
    return spec.StoredPreregistration(
        pubkey=xmss_pubkeys[index],
        withdrawal_credentials=withdrawal_credentials,
        vrf_root=get_vrf_root(index),
        expiry_slot=expiry_slot,
    )
