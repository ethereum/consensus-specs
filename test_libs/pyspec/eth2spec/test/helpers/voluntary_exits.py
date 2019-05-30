from eth2spec.utils.bls import bls_sign
from eth2spec.utils.minimal_ssz import signing_root


def build_voluntary_exit(spec, state, epoch, validator_index, privkey, signed=False):
    voluntary_exit = spec.VoluntaryExit(
        epoch=epoch,
        validator_index=validator_index,
    )
    if signed:
        sign_voluntary_exit(spec, state, voluntary_exit, privkey)
    return voluntary_exit


def sign_voluntary_exit(spec, state, voluntary_exit, privkey):
    voluntary_exit.signature = bls_sign(
        message_hash=signing_root(voluntary_exit),
        privkey=privkey,
        domain=spec.get_domain(
            state=state,
            domain_type=spec.DOMAIN_VOLUNTARY_EXIT,
            message_epoch=voluntary_exit.epoch,
        )
    )
