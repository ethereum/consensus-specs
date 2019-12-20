from eth2spec.utils import bls


def sign_block_header(spec, state, header, privkey):
    domain = spec.get_domain(
        state=state,
        domain_type=spec.DOMAIN_BEACON_PROPOSER,
    )
    message = spec.compute_domain_wrapper_root(header, domain)
    signature = bls.Sign(privkey, message)
    return spec.SignedBeaconBlockHeader(message=header, signature=signature)
