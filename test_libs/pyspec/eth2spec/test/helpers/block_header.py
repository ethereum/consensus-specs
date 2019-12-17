from eth2spec.utils.bls import Sign
from eth2spec.utils.ssz.ssz_impl import hash_tree_root


def sign_block_header(spec, state, header, privkey):
    domain = spec.get_domain(
        state=state,
        domain_type=spec.DOMAIN_BEACON_PROPOSER,
    )
    message = spec.compute_domain_wrapper_root(header, domain)
    signature = Sign(privkey, message)
    return spec.SignedBeaconBlockHeader(message=header, signature=signature)
