from eth2spec.test.context import (
    with_phases,
    with_custom_state,
    with_presets,
    spec_test, with_state,
    low_balances, misc_balances, large_validator_set,
)
from eth2spec.test.utils import with_meta_tags
from eth2spec.test.helpers.constants import (
    DENEB, ELECTRA,
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
@with_custom_state(balances_fn=low_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@spec_test
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_random_low_balances(spec, phases, state):
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@with_custom_state(balances_fn=misc_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@spec_test
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_random_misc_balances(spec, phases, state):
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@with_presets([MINIMAL],
              reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated")
@with_custom_state(balances_fn=large_validator_set, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@spec_test
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_random_large_validator_set(spec, phases, state):
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_pre_activation(spec, phases, state):
    post_spec = phases[ELECTRA]
    state.validators[0].activation_epoch = spec.FAR_FUTURE_EPOCH
    post_state = yield from run_fork_test(post_spec, state)

    assert len(post_state.pending_balance_deposits) > 0


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_fork_has_compounding_withdrawal_credential(spec, phases, state):
    post_spec = phases[ELECTRA]
    validator = state.validators[0]
    state.balances[0] = post_spec.MIN_ACTIVATION_BALANCE + 1
    validator.withdrawal_credentials = post_spec.COMPOUNDING_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]
    post_state = yield from run_fork_test(post_spec, state)

    assert len(post_state.pending_balance_deposits) > 0
