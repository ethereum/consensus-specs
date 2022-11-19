from .constants import (
    PHASE0, ALTAIR, BELLATRIX, CAPELLA, EIP4844,
)


def is_post_fork(a, b):
    if a == EIP4844:
        return b in [PHASE0, ALTAIR, BELLATRIX, CAPELLA, EIP4844]
    if a == CAPELLA:
        return b in [PHASE0, ALTAIR, BELLATRIX, CAPELLA]
    if a == BELLATRIX:
        return b in [PHASE0, ALTAIR, BELLATRIX]
    if a == ALTAIR:
        return b in [PHASE0, ALTAIR]
    if a == PHASE0:
        return b in [PHASE0]
    raise ValueError("Unknown fork name %s" % a)


def is_post_altair(spec):
    return is_post_fork(spec.fork, ALTAIR)


def is_post_bellatrix(spec):
    return is_post_fork(spec.fork, BELLATRIX)


def is_post_capella(spec):
    return is_post_fork(spec.fork, CAPELLA)


def is_post_eip4844(spec):
    return is_post_fork(spec.fork, EIP4844)
