from eth2spec.test.context import (
    spec_state_test,
    always_bls,
    with_bellatrix_and_later,
)
from eth2spec.test.helpers.deposits import (
    deposit_from_context,
    run_deposit_processing,
)
from eth2spec.test.helpers.keys import (
    privkeys,
    pubkeys,
)
from eth2spec.utils import bls


def _run_deposit_processing_with_specific_fork_version(
        spec,
        state,
        fork_version,
        valid,
        effective):
    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE

    pubkey = pubkeys[validator_index]
    privkey = privkeys[validator_index]
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(pubkey)[1:]

    deposit_message = spec.DepositMessage(pubkey=pubkey, withdrawal_credentials=withdrawal_credentials, amount=amount)
    domain = spec.compute_domain(domain_type=spec.DOMAIN_DEPOSIT, fork_version=fork_version)
    deposit_data = spec.DepositData(
        pubkey=pubkey, withdrawal_credentials=withdrawal_credentials, amount=amount,
        signature=bls.Sign(privkey, spec.compute_signing_root(deposit_message, domain))
    )
    deposit, root, _ = deposit_from_context(spec, [deposit_data], 0)

    state.eth1_deposit_index = 0
    state.eth1_data.deposit_root = root
    state.eth1_data.deposit_count = 1

    yield from run_deposit_processing(spec, state, deposit, validator_index, valid=valid, effective=effective)


@with_bellatrix_and_later
@spec_state_test
@always_bls
def test_deposit_with_previous_fork_version__valid_ineffective(spec, state):
    assert state.fork.previous_version != state.fork.current_version

    yield from _run_deposit_processing_with_specific_fork_version(
        spec,
        state,
        fork_version=state.fork.previous_version,
        valid=True,
        effective=False,
    )


@with_bellatrix_and_later
@spec_state_test
@always_bls
def test_deposit_with_genesis_fork_version__valid_effective(spec, state):
    assert spec.config.GENESIS_FORK_VERSION not in (state.fork.previous_version, state.fork.current_version)

    yield from _run_deposit_processing_with_specific_fork_version(
        spec,
        state,
        fork_version=spec.config.GENESIS_FORK_VERSION,
        valid=True,
        effective=True,
    )


@with_bellatrix_and_later
@spec_state_test
@always_bls
def test_deposit_with_bad_fork_version__valid_ineffective(spec, state):
    yield from _run_deposit_processing_with_specific_fork_version(
        spec,
        state,
        fork_version=spec.Version('0xAaBbCcDd'),
        valid=True,
        effective=False,
    )
