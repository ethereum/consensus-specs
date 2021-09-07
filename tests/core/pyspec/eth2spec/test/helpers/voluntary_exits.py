from random import Random
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


#
# Helpers for applying effects of a voluntary exit
#
def get_exited_validators(spec, state):
    current_epoch = spec.get_current_epoch(state)
    return [index for (index, validator) in enumerate(state.validators) if validator.exit_epoch <= current_epoch]


def get_unslashed_exited_validators(spec, state):
    return [
        index for index in get_exited_validators(spec, state)
        if not state.validators[index].slashed
    ]


def exit_validators(spec, state, validator_count, rng=None):
    if rng is None:
        rng = Random(1337)

    indices = rng.sample(range(len(state.validators)), validator_count)
    for index in indices:
        spec.initiate_validator_exit(state, index)
    return indices
