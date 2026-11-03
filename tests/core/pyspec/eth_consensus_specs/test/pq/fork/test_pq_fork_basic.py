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
from eth_consensus_specs.test.helpers.keys import xmss_pubkeys
from eth_consensus_specs.test.helpers.pq.fork import (
    PQ_FORK_TEST_META_TAGS,
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
    post_state = yield from run_fork_test(phases[PQ], state)

    post_spec = phases[PQ]
    for index, validator in enumerate(post_state.validators):
        assert validator.pubkey == xmss_pubkeys[index]
        assert validator.exit_epoch == post_spec.FAR_FUTURE_EPOCH


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
def test_fork_duplicate_registration(spec, phases, state):
    register_xmss_pubkeys(spec, state)
    # Validator 1 registers the key of validator 0
    state.pq_registrations[1].pq_data = state.pq_registrations[0].pq_data
    post_state = yield from run_fork_test(phases[PQ], state)

    post_spec = phases[PQ]
    for index in (0, 1):
        assert post_state.validators[index].pubkey == post_spec.compute_unusable_xmss_pubkey(
            state.validators[index].pubkey
        )
        assert post_state.validators[index].exit_epoch != post_spec.FAR_FUTURE_EPOCH
    assert post_state.validators[2].pubkey == xmss_pubkeys[2]
    assert post_state.validators[2].exit_epoch == post_spec.FAR_FUTURE_EPOCH


@with_phases(phases=[EIP8483], other_phases=[PQ])
@spec_test
@with_state
@with_meta_tags(PQ_FORK_TEST_META_TAGS)
def test_fork_pending_top_up_deposit(spec, phases, state):
    register_xmss_pubkeys(spec, state)
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    state.pending_deposits.append(prepare_pending_deposit(spec, 0, amount, signed=True))
    post_state = yield from run_fork_test(phases[PQ], state)

    post_spec = phases[PQ]
    assert len(post_state.pending_deposits) == 1
    deposit = post_state.pending_deposits[0]
    assert deposit.pubkey == xmss_pubkeys[0]
    assert deposit.amount == amount
    assert deposit.signature == post_spec.XMSSSignature()
    assert len(post_state.validators) == len(state.validators)


@with_phases(phases=[EIP8483], other_phases=[PQ])
@spec_test
@with_state
@with_meta_tags(PQ_FORK_TEST_META_TAGS)
def test_fork_pending_new_validator_deposit(spec, phases, state):
    register_xmss_pubkeys(spec, state)
    new_index = len(state.validators)
    amount = spec.MIN_ACTIVATION_BALANCE
    pending_deposit = prepare_pending_deposit(spec, new_index, amount, signed=True)
    state.pending_deposits.append(pending_deposit)
    post_state = yield from run_fork_test(phases[PQ], state)

    post_spec = phases[PQ]
    assert len(post_state.validators) == new_index + 1
    new_validator = post_state.validators[new_index]
    assert new_validator.pubkey == post_spec.compute_unusable_xmss_pubkey(pending_deposit.pubkey)
    assert new_validator.exit_epoch != post_spec.FAR_FUTURE_EPOCH
    assert post_state.balances[new_index] == 0
    assert len(post_state.pending_deposits) == 1
    assert post_state.pending_deposits[0].pubkey == new_validator.pubkey
    assert post_state.pending_deposits[0].amount == amount


@with_phases(phases=[EIP8483], other_phases=[PQ])
@spec_test
@with_state
@with_meta_tags(PQ_FORK_TEST_META_TAGS)
def test_fork_pending_deposit_invalid_signature(spec, phases, state):
    register_xmss_pubkeys(spec, state)
    new_index = len(state.validators)
    state.pending_deposits.append(
        prepare_pending_deposit(spec, new_index, spec.MIN_ACTIVATION_BALANCE, signed=False)
    )
    post_state = yield from run_fork_test(phases[PQ], state)

    assert len(post_state.validators) == new_index
    assert len(post_state.pending_deposits) == 0


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
