from .constants import (
    ALTAIR, BELLATRIX, CAPELLA, DENEB,
    EIP6110, EIP7002, WHISK,
    PREVIOUS_FORK_OF,
)


def is_post_fork(a, b) -> bool:
    """
    Returns true if fork a is after b, or if a == b
    """
    if a == b:
        return True

    prev_fork = PREVIOUS_FORK_OF[a]
    if prev_fork == b:
        return True
    elif prev_fork is None:
        return False
    else:
        return is_post_fork(prev_fork, b)


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


def is_post_whisk(spec):
    return is_post_fork(spec.fork, WHISK)
