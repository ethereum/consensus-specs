from .constants import (
    PHASE0, ALTAIR, BELLATRIX, CAPELLA, DENEB,
    EIP6110, EIP7002,
)


def is_post_fork(a, b):
    if a == EIP7002:
        return b in [PHASE0, ALTAIR, BELLATRIX, CAPELLA, EIP7002]
    if a == EIP6110:
        return b in [PHASE0, ALTAIR, BELLATRIX, CAPELLA, DENEB, EIP6110]
    if a == DENEB:
        return b in [PHASE0, ALTAIR, BELLATRIX, CAPELLA, DENEB]
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


def is_post_deneb(spec):
    return is_post_fork(spec.fork, DENEB)


def is_post_eip6110(spec):
    return is_post_fork(spec.fork, EIP6110)


def is_post_eip7002(spec):
    return is_post_fork(spec.fork, EIP7002)
