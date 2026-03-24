from .constants import (
    ALTAIR,
    BELLATRIX,
    CAPELLA,
    DENEB,
    EIP7928,
    EIP8025,
    ELECTRA,
    FULU,
    GLOAS,
    HEZE,
    PHASE0,
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


def is_post_electra(spec):
    return is_post_fork(spec.fork, ELECTRA)


def is_post_fulu(spec):
    return is_post_fork(spec.fork, FULU)


def is_post_gloas(spec):
    return is_post_fork(spec.fork, GLOAS)


def is_post_heze(spec):
    return is_post_fork(spec.fork, HEZE)


def is_post_eip7928(spec):
    return is_post_fork(spec.fork, EIP7928)


def is_post_eip8025(spec):
    return is_post_fork(spec.fork, EIP8025)


def has_explicit_fork_version(spec, fork) -> bool:
    if fork == PHASE0:
        return True
    return hasattr(spec.config, fork.upper() + "_FORK_VERSION")


def get_fork_version(spec, fork):
    while fork != PHASE0 and not has_explicit_fork_version(spec, fork):
        fork = PREVIOUS_FORK_OF[fork]

    if fork == PHASE0:
        return spec.config.GENESIS_FORK_VERSION

    return getattr(spec.config, fork.upper() + "_FORK_VERSION")


def get_fork_epoch(spec, fork):
    if fork == PHASE0:
        return spec.GENESIS_EPOCH

    return getattr(spec.config, fork.upper() + "_FORK_EPOCH", None)


def get_spec_for_fork_version(spec, fork_version, phases):
    if phases is None:
        return spec
    for fork in [fork for fork in phases if is_post_fork(spec.fork, fork)]:
        if not has_explicit_fork_version(spec, fork):
            continue
        if fork_version == get_fork_version(spec, fork):
            return phases[fork]
    raise ValueError(f"Unknown fork version {fork_version}")


def get_next_fork_transition(spec, epoch, phases):
    if phases is None:
        return None, None
    for fork in [fork for fork in phases if PREVIOUS_FORK_OF[fork] == spec.fork]:
        assert fork != PHASE0  # PHASE0 does not have previous fork
        fork_epoch = get_fork_epoch(phases[fork], fork)
        if fork_epoch is None:
            continue
        assert fork_epoch > epoch  # Forks through given epoch already applied
        return phases[fork], fork_epoch
    return None, None  # Already at latest fork
