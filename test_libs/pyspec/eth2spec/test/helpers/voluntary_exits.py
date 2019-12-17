from eth2spec.utils.bls import Sign


def sign_voluntary_exit(spec, state, voluntary_exit, privkey):
    domain = spec.get_domain(state, spec.DOMAIN_VOLUNTARY_EXIT, voluntary_exit.epoch)
    message = spec.compute_domain_wrapper_root(voluntary_exit, domain)
    return spec.SignedVoluntaryExit(
        message=voluntary_exit,
        signature=Sign(privkey, message)
    )
