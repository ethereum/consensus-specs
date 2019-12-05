from eth2spec.utils.bls import bls_sign
from eth2spec.utils.ssz.ssz_impl import hash_tree_root


def sign_voluntary_exit(spec, state, voluntary_exit, privkey):
    return spec.SignedVoluntaryExit(
        message=voluntary_exit,
        signature=bls_sign(
            message_hash=hash_tree_root(voluntary_exit),
            privkey=privkey,
            domain=spec.get_domain(
                state=state,
                domain_type=spec.DOMAIN_VOLUNTARY_EXIT,
                message_epoch=voluntary_exit.epoch,
            )
        )
    )
