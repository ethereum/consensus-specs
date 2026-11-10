from eth_consensus_specs.test.context import (
    spec_test,
    with_phases,
    with_state,
)
from eth_consensus_specs.test.helpers.constants import (
    EIP8483,
    PQ,
)
from eth_consensus_specs.test.helpers.deposits import prepare_pending_deposit
from eth_consensus_specs.test.helpers.keys import xmss_builder_pubkeys, xmss_pubkeys
from eth_consensus_specs.test.helpers.pq.fork import (
    PQ_FORK_TEST_META_TAGS,
    register_builder_xmss_pubkeys,
    register_xmss_pubkeys,
    run_fork_test,
)
from eth_consensus_specs.test.helpers.state import (
    next_epoch,
    next_epoch_via_block,
)
from eth_consensus_specs.test.utils import with_meta_tags


@with_phases(phases=[EIP8483], other_phases=[PQ])
@spec_test
@with_state
@with_meta_tags(PQ_FORK_TEST_META_TAGS)
def test_fork_all_registered(spec, phases, state):
    register_xmss_pubkeys(spec, state)
    register_builder_xmss_pubkeys(spec, state)
    post_state = yield from run_fork_test(phases[PQ], state)

    post_spec = phases[PQ]
    for index, validator in enumerate(post_state.validators):
        assert validator.pubkey == xmss_pubkeys[index]
        assert validator.exit_epoch == post_spec.FAR_FUTURE_EPOCH
    assert len(post_state.builders) > 0
    for index, builder in enumerate(post_state.builders):
        assert builder.pubkey == xmss_builder_pubkeys[index]
        assert builder.withdrawable_epoch == post_spec.FAR_FUTURE_EPOCH


@with_phases(phases=[EIP8483], other_phases=[PQ])
@spec_test
@with_state
@with_meta_tags(PQ_FORK_TEST_META_TAGS)
def test_fork_builders_not_registered(spec, phases, state):
    register_xmss_pubkeys(spec, state)
    post_state = yield from run_fork_test(phases[PQ], state)

    post_spec = phases[PQ]
    assert len(post_state.builders) > 0
    for pre_builder, builder in zip(state.builders, post_state.builders, strict=True):
        assert builder.pubkey == post_spec.sha256(
            pre_builder.pubkey + post_spec.LEGACY_XMSS_PUBKEY_DOMAIN
        )
        assert builder.withdrawable_epoch != post_spec.FAR_FUTURE_EPOCH


@with_phases(phases=[EIP8483], other_phases=[PQ])
@spec_test
@with_state
@with_meta_tags(PQ_FORK_TEST_META_TAGS)
def test_fork_builder_shares_validator_pubkey(spec, phases, state):
    state.builders[0].pubkey = state.validators[0].pubkey
    register_xmss_pubkeys(spec, state)
    register_builder_xmss_pubkeys(spec, state)
    post_state = yield from run_fork_test(phases[PQ], state)

    post_spec = phases[PQ]
    assert post_state.validators[0].pubkey == xmss_pubkeys[0]
    assert post_state.builders[0].pubkey == xmss_builder_pubkeys[0]
    assert post_state.validators[0].exit_epoch == post_spec.FAR_FUTURE_EPOCH
    assert post_state.builders[0].withdrawable_epoch == post_spec.FAR_FUTURE_EPOCH


@with_phases(phases=[EIP8483], other_phases=[PQ])
@spec_test
@with_state
@with_meta_tags(PQ_FORK_TEST_META_TAGS)
def test_fork_no_registrations(spec, phases, state):
    post_state = yield from run_fork_test(phases[PQ], state)

    post_spec = phases[PQ]
    for validator in post_state.validators:
        assert validator.exit_epoch != post_spec.FAR_FUTURE_EPOCH


@with_phases(phases=[EIP8483], other_phases=[PQ])
@spec_test
@with_state
@with_meta_tags(PQ_FORK_TEST_META_TAGS)
def test_fork_partially_registered(spec, phases, state):
    registered_indices = range(0, len(state.validators), 2)
    register_xmss_pubkeys(spec, state, registered_indices)
    post_state = yield from run_fork_test(phases[PQ], state)

    post_spec = phases[PQ]
    for index, validator in enumerate(post_state.validators):
        is_registered = index in registered_indices
        assert (validator.exit_epoch == post_spec.FAR_FUTURE_EPOCH) == is_registered


@with_phases(phases=[EIP8483], other_phases=[PQ])
@spec_test
@with_state
@with_meta_tags(PQ_FORK_TEST_META_TAGS)
def test_fork_slashed_validator_not_registered(spec, phases, state):
    slashed_index = 0
    spec.slash_validator(state, slashed_index)
    register_xmss_pubkeys(spec, state, range(1, len(state.validators)))
    pre_withdrawable_epoch = state.validators[slashed_index].withdrawable_epoch
    post_state = yield from run_fork_test(phases[PQ], state)

    validator = post_state.validators[slashed_index]
    assert validator.slashed
    assert validator.exit_epoch <= post_state.fork.epoch
    assert validator.withdrawable_epoch == pre_withdrawable_epoch
    assert validator.withdrawable_epoch > post_state.fork.epoch


@with_phases(phases=[EIP8483], other_phases=[PQ])
@spec_test
@with_state
@with_meta_tags(PQ_FORK_TEST_META_TAGS)
def test_fork_pending_top_up_deposit(spec, phases, state):
    register_xmss_pubkeys(spec, state)
    state.pending_deposits.append(
        prepare_pending_deposit(spec, 0, spec.EFFECTIVE_BALANCE_INCREMENT, signed=True)
    )
    yield from run_fork_test(phases[PQ], state)


@with_phases(phases=[EIP8483], other_phases=[PQ])
@spec_test
@with_state
@with_meta_tags(PQ_FORK_TEST_META_TAGS)
def test_fork_pending_top_up_deposit_not_registered(spec, phases, state):
    state.pending_deposits.append(
        prepare_pending_deposit(spec, 0, spec.EFFECTIVE_BALANCE_INCREMENT, signed=True)
    )
    yield from run_fork_test(phases[PQ], state)


@with_phases(phases=[EIP8483], other_phases=[PQ])
@spec_test
@with_state
@with_meta_tags(PQ_FORK_TEST_META_TAGS)
def test_fork_pending_new_validator_deposit(spec, phases, state):
    register_xmss_pubkeys(spec, state)
    new_index = len(state.validators)
    state.pending_deposits.append(
        prepare_pending_deposit(spec, new_index, spec.MIN_ACTIVATION_BALANCE, signed=True)
    )
    yield from run_fork_test(phases[PQ], state)


@with_phases(phases=[EIP8483], other_phases=[PQ])
@spec_test
@with_state
@with_meta_tags(PQ_FORK_TEST_META_TAGS)
def test_fork_next_epoch(spec, phases, state):
    register_xmss_pubkeys(spec, state)
    next_epoch(spec, state)
    yield from run_fork_test(phases[PQ], state)


@with_phases(phases=[EIP8483], other_phases=[PQ])
@spec_test
@with_state
@with_meta_tags(PQ_FORK_TEST_META_TAGS)
def test_fork_next_epoch_with_block(spec, phases, state):
    register_xmss_pubkeys(spec, state)
    next_epoch_via_block(spec, state)
    yield from run_fork_test(phases[PQ], state)
