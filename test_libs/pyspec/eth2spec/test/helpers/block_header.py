# Access constants from spec pkg reference.
import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import get_domain
from eth2spec.utils.bls import bls_sign
from eth2spec.utils.ssz.ssz_impl import signing_root


def sign_block_header(state, header, privkey):
    domain = get_domain(
        state=state,
        domain_type=spec.DOMAIN_BEACON_PROPOSER,
    )
    header.signature = bls_sign(
        message_hash=signing_root(header),
        privkey=privkey,
        domain=domain,
    )
