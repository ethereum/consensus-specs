from random import Random
from eth2spec.utils import bls
from eth2spec.test.context import expect_assertion_error
from eth2spec.test.helpers.forks import is_post_deneb
from eth2spec.test.helpers.keys import privkeys


def prepare_signed_exits(spec, state, indices, fork_version=None):
    def create_signed_exit(index):
        voluntary_exit = spec.VoluntaryExit(
            epoch=spec.get_current_epoch(state),
            validator_index=index,
        )
        return sign_voluntary_exit(
            spec, state, voluntary_exit, privkeys[index], fork_version=fork_version
        )

    return [create_signed_exit(index) for index in indices]


def sign_voluntary_exit(spec, state, voluntary_exit, privkey, fork_version=None):
    if fork_version is None:
        if is_post_deneb(spec):
            domain = spec.compute_domain(
                spec.DOMAIN_VOLUNTARY_EXIT,
                spec.config.CAPELLA_FORK_VERSION,
                state.genesis_validators_root,
            )
        else:
            domain = spec.get_domain(state, spec.DOMAIN_VOLUNTARY_EXIT, voluntary_exit.epoch)
    else:
        domain = spec.compute_domain(
            spec.DOMAIN_VOLUNTARY_EXIT, fork_version, state.genesis_validators_root
        )

    signing_root = spec.compute_signing_root(voluntary_exit, domain)
    return spec.SignedVoluntaryExit(
        message=voluntary_exit, signature=bls.Sign(privkey, signing_root)
    )


#
# Helpers for applying effects of a voluntary exit
#
def get_exited_validators(spec, state):
    current_epoch = spec.get_current_epoch(state)
    return [
        index
        for (index, validator) in enumerate(state.validators)
        if validator.exit_epoch <= current_epoch
    ]


def get_unslashed_exited_validators(spec, state):
    return [
        index for index in get_exited_validators(spec, state) if not state.validators[index].slashed
    ]


def exit_validators(spec, state, validator_count, rng=None):
    if rng is None:
        rng = Random(1337)

    indices = rng.sample(range(len(state.validators)), validator_count)
    for index in indices:
        spec.initiate_validator_exit(state, index)
    return indices


#
# Run processing
#


def run_voluntary_exit_processing(spec, state, signed_voluntary_exit, valid=True):
    """
    Run ``process_voluntary_exit``, yielding:
      - pre-state ('pre')
      - voluntary_exit ('voluntary_exit')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    validator_index = signed_voluntary_exit.message.validator_index

    yield "pre", state
    yield "voluntary_exit", signed_voluntary_exit

    if not valid:
        expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
        yield "post", None
        return

    pre_exit_epoch = state.validators[validator_index].exit_epoch

    spec.process_voluntary_exit(state, signed_voluntary_exit)

    yield "post", state

    assert pre_exit_epoch == spec.FAR_FUTURE_EPOCH
    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH
