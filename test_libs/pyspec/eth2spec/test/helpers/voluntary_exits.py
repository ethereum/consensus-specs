# Access constants from spec pkg reference.
import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import VoluntaryExit, get_domain
from eth2spec.utils.bls import bls_sign
from eth2spec.utils.minimal_ssz import signing_root


def build_voluntary_exit(state, epoch, validator_index, privkey):
    voluntary_exit = VoluntaryExit(
        epoch=epoch,
        validator_index=validator_index,
    )
    voluntary_exit.signature = bls_sign(
        message_hash=signing_root(voluntary_exit),
        privkey=privkey,
        domain=get_domain(
            state=state,
            domain_type=spec.DOMAIN_VOLUNTARY_EXIT,
            message_epoch=epoch,
        )
    )

    return voluntary_exit
