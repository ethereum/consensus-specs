from eth_consensus_specs.utils import bls


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
