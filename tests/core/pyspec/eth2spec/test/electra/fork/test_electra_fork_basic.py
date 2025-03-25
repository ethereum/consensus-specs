from eth2spec.test.context import (
    with_phases,
    with_custom_state,
    with_presets,
    spec_test,
    with_state,
    low_balances,
    misc_balances,
    large_validator_set,
)
from eth2spec.test.utils import with_meta_tags
from eth2spec.test.helpers.constants import (
    DENEB,
    ELECTRA,
    MINIMAL,
)
from eth2spec.test.helpers.state import (
    next_epoch,
    next_epoch_via_block,
)
from eth2spec.test.helpers.electra.fork import (
    ELECTRA_FORK_TEST_META_TAGS,
    run_fork_test,
)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_base_state(spec, phases, state):
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_next_epoch(spec, phases, state):
    next_epoch(spec, state)
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_next_epoch_with_block(spec, phases, state):
    next_epoch_via_block(spec, state)
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_many_next_epoch(spec, phases, state):
    for _ in range(3):
        next_epoch(spec, state)
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@with_custom_state(
    balances_fn=low_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE
)
@spec_test
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_random_low_balances(spec, phases, state):
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@with_custom_state(
    balances_fn=misc_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE
)
@spec_test
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_random_misc_balances(spec, phases, state):
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@with_presets(
    [MINIMAL],
    reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated",
)
@with_custom_state(
    balances_fn=large_validator_set,
    threshold_fn=lambda spec: spec.config.EJECTION_BALANCE,
)
@spec_test
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_random_large_validator_set(spec, phases, state):
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_pre_activation(spec, phases, state):
    index = 0
    post_spec = phases[ELECTRA]
    state.validators[index].activation_epoch = spec.FAR_FUTURE_EPOCH
    post_state = yield from run_fork_test(post_spec, state)

    validator = post_state.validators[index]
    assert post_state.balances[index] == 0
    assert validator.effective_balance == 0
    assert validator.activation_eligibility_epoch == spec.FAR_FUTURE_EPOCH
    assert post_state.pending_deposits == [
        post_spec.PendingDeposit(
            pubkey=validator.pubkey,
            withdrawal_credentials=validator.withdrawal_credentials,
            amount=state.balances[index],
            signature=spec.bls.G2_POINT_AT_INFINITY,
            slot=spec.GENESIS_SLOT,
        )
    ]


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_pending_deposits_are_sorted(spec, phases, state):
    post_spec = phases[ELECTRA]
    state.validators[0].activation_epoch = spec.FAR_FUTURE_EPOCH
    state.validators[0].activation_eligibility_epoch = 2
    state.validators[1].activation_epoch = spec.FAR_FUTURE_EPOCH
    state.validators[1].activation_eligibility_epoch = 3
    state.validators[2].activation_epoch = spec.FAR_FUTURE_EPOCH
    state.validators[2].activation_eligibility_epoch = 2
    state.validators[3].activation_epoch = spec.FAR_FUTURE_EPOCH
    state.validators[3].activation_eligibility_epoch = 1

    post_state = yield from run_fork_test(post_spec, state)

    assert len(post_state.pending_deposits) == 4
    assert post_state.pending_deposits[0].pubkey == state.validators[3].pubkey
    assert post_state.pending_deposits[1].pubkey == state.validators[0].pubkey
    assert post_state.pending_deposits[2].pubkey == state.validators[2].pubkey
    assert post_state.pending_deposits[3].pubkey == state.validators[1].pubkey


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_has_compounding_withdrawal_credential(spec, phases, state):
    index = 0
    post_spec = phases[ELECTRA]
    validator = state.validators[index]
    state.balances[index] = post_spec.MIN_ACTIVATION_BALANCE + 1
    validator.withdrawal_credentials = (
        post_spec.COMPOUNDING_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]
    )
    post_state = yield from run_fork_test(post_spec, state)

    assert post_state.balances[index] == post_spec.MIN_ACTIVATION_BALANCE
    assert post_state.pending_deposits == [
        post_spec.PendingDeposit(
            pubkey=validator.pubkey,
            withdrawal_credentials=validator.withdrawal_credentials,
            amount=state.balances[index] - post_spec.MIN_ACTIVATION_BALANCE,
            signature=spec.bls.G2_POINT_AT_INFINITY,
            slot=spec.GENESIS_SLOT,
        )
    ]


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_inactive_compounding_validator_with_excess_balance(spec, phases, state):
    index = 0
    post_spec = phases[ELECTRA]
    validator = state.validators[index]

    # set validator balance greater than min_activation_balance
    state.balances[index] = post_spec.MIN_ACTIVATION_BALANCE + 1
    # set validator as not active yet
    validator.activation_epoch = spec.FAR_FUTURE_EPOCH
    # set validator activation eligibility epoch to the latest finalized epoch
    validator.activation_eligibility_epoch = state.finalized_checkpoint.epoch
    # give the validator compounding withdrawal credentials
    validator.withdrawal_credentials = (
        post_spec.COMPOUNDING_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]
    )

    post_state = yield from run_fork_test(post_spec, state)

    # the validator cannot be activated again
    assert (
        post_state.validators[index].activation_eligibility_epoch
        == spec.FAR_FUTURE_EPOCH
    )
    # the validator should now have a zero balance
    assert post_state.balances[index] == 0
    # there should be a single pending deposit for this validator
    assert post_state.pending_deposits == [
        post_spec.PendingDeposit(
            pubkey=validator.pubkey,
            withdrawal_credentials=validator.withdrawal_credentials,
            amount=state.balances[index],
            signature=spec.bls.G2_POINT_AT_INFINITY,
            slot=spec.GENESIS_SLOT,
        )
    ]


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_earliest_exit_epoch_no_validator_exits(spec, phases, state):
    # advance state so the current epoch is not zero
    next_epoch(spec, state)
    next_epoch(spec, state)
    next_epoch(spec, state)

    post_spec = phases[ELECTRA]
    post_state = yield from run_fork_test(post_spec, state)

    # the earliest exit epoch should be the compute_activation_exit_epoch + 1
    current_epoch = post_spec.compute_epoch_at_slot(post_state.slot)
    expected_earliest_exit_epoch = (
        post_spec.compute_activation_exit_epoch(current_epoch) + 1
    )
    assert post_state.earliest_exit_epoch == expected_earliest_exit_epoch


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_earliest_exit_epoch_is_max_validator_exit_epoch(spec, phases, state):
    # assign some validators exit epochs
    state.validators[0].exit_epoch = 20
    state.validators[1].exit_epoch = 30
    state.validators[2].exit_epoch = 10

    post_state = yield from run_fork_test(phases[ELECTRA], state)

    # the earliest exit epoch should be the greatest validator exit epoch + 1
    expected_earliest_exit_epoch = post_state.validators[1].exit_epoch + 1
    assert post_state.earliest_exit_epoch == expected_earliest_exit_epoch


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_earliest_exit_epoch_less_than_current_epoch(spec, phases, state):
    # assign a validator an exit epoch
    state.validators[0].exit_epoch = 1

    # advance state so the current epoch is not zero
    next_epoch(spec, state)
    next_epoch(spec, state)
    next_epoch(spec, state)

    post_spec = phases[ELECTRA]
    post_state = yield from run_fork_test(post_spec, state)

    # the earliest exit epoch should be the compute_activation_exit_epoch + 1
    current_epoch = post_spec.compute_epoch_at_slot(post_state.slot)
    expected_earliest_exit_epoch = (
        post_spec.compute_activation_exit_epoch(current_epoch) + 1
    )
    assert post_state.earliest_exit_epoch == expected_earliest_exit_epoch
