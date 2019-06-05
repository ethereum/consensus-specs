from eth2spec.utils.bls import bls_sign
from eth2spec.utils.ssz.ssz_impl import signing_root


def sign_block_header(spec, state, header, privkey):
    domain = spec.get_domain(
        state=state,
        domain_type=spec.DOMAIN_BEACON_PROPOSER,
    )
    header.signature = bls_sign(
        message_hash=signing_root(header),
        privkey=privkey,
        domain=domain,
    )
