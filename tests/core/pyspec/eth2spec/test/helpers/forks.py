from .constants import (
    ALTAIR,
    BELLATRIX,
    CAPELLA,
    DENEB,
    EIP7441,
    EIP7732,
    EIP7805,
    ELECTRA,
    FULU,
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


def is_post_eip7441(spec):
    return is_post_fork(spec.fork, EIP7441)


def is_post_eip7732(spec):
    return is_post_fork(spec.fork, EIP7732)


def is_post_eip7805(spec):
    return is_post_fork(spec.fork, EIP7805)


def get_spec_for_fork_version(spec, fork_version, phases):
    if phases is None:
        return spec
    for fork in [fork for fork in phases if is_post_fork(spec.fork, fork)]:
        if fork == PHASE0:
            fork_version_field = "GENESIS_FORK_VERSION"
        else:
            fork_version_field = fork.upper() + "_FORK_VERSION"
        if fork_version == getattr(spec.config, fork_version_field):
            return phases[fork]
    raise ValueError(f"Unknown fork version {fork_version}")


def get_next_fork_transition(spec, epoch, phases):
    if phases is None:
        return None, None
    for fork in [fork for fork in phases if PREVIOUS_FORK_OF[fork] == spec.fork]:
        assert fork != PHASE0  # PHASE0 does not have previous fork
        fork_epoch = getattr(phases[fork].config, fork.upper() + "_FORK_EPOCH")
        assert fork_epoch > epoch  # Forks through given epoch already applied
        return phases[fork], fork_epoch
    return None, None  # Already at latest fork
