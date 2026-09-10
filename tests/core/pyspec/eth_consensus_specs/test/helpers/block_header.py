from eth_consensus_specs.utils import bls


def sign_block_header(spec, state, header, privkey):
    domain = spec.get_domain(
        state=state,
        domain_type=spec.DOMAIN_BEACON_PROPOSER,
    )
    signing_root = spec.compute_signing_root(header, domain)
    signature = bls.Sign(privkey, signing_root)
    return spec.SignedBeaconBlockHeader(message=header, signature=signature)
