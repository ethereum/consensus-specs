from eth2spec.utils import bls
from eth2spec.test.helpers.keys import privkeys


def prepare_signed_exits(spec, state, indices):
    domain = spec.get_domain(state, spec.DOMAIN_VOLUNTARY_EXIT)

    def create_signed_exit(index):
        exit = spec.VoluntaryExit(
            epoch=spec.get_current_epoch(state),
            validator_index=index,
        )
        signing_root = spec.compute_signing_root(exit, domain)
        return spec.SignedVoluntaryExit(message=exit, signature=bls.Sign(privkeys[index], signing_root))

    return [create_signed_exit(index) for index in indices]


def sign_voluntary_exit(spec, state, voluntary_exit, privkey):
    domain = spec.get_domain(state, spec.DOMAIN_VOLUNTARY_EXIT, voluntary_exit.epoch)
    signing_root = spec.compute_signing_root(voluntary_exit, domain)
    return spec.SignedVoluntaryExit(
        message=voluntary_exit,
        signature=bls.Sign(privkey, signing_root)
    )
