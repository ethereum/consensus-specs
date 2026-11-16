from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.keys import xmss_pubkeys


def advance_past_shard_committee_period(spec, state):
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH


def prepare_voluntary_exit_request(spec, state, validator_index):
    """
    A voluntary exit request naming the XMSS public key of the validator at
    ``validator_index``.
    """
    return spec.VoluntaryExitRequest(pubkey=state.validators[validator_index].pubkey)


def run_voluntary_exit_request_processing(spec, state, voluntary_exit_request, valid=True):
    """
    Run ``process_voluntary_exit_request``, yielding:
      - pre-state ('pre')
      - voluntary_exit_request ('voluntary_exit_request')
      - post-state ('post').

    The function never raises. If valid is False, expect the request to be
    consumed without changing the state.
    """
    pre_state = state.copy()

    yield "pre", state
    yield "voluntary_exit_request", voluntary_exit_request

    spec.process_voluntary_exit_request(state, voluntary_exit_request)

    yield "post", state

    if not valid:
        assert state == pre_state


@with_phases([PQ])
@spec_state_test
def test_voluntary_exit_request(spec, state):
    advance_past_shard_committee_period(spec, state)
    validator_index = 0
    voluntary_exit_request = prepare_voluntary_exit_request(spec, state, validator_index)

    yield from run_voluntary_exit_request_processing(spec, state, voluntary_exit_request)

    validator = state.validators[validator_index]
    assert validator.exit_epoch == spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    assert validator.withdrawable_epoch == (
        validator.exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )


@with_phases([PQ])
@spec_state_test
def test_voluntary_exit_request_bls_withdrawal_credentials(spec, state):
    advance_past_shard_committee_period(spec, state)
    validator_index = 0
    # The validator has no withdrawal address, but its exit needs none
    state.validators[validator_index].withdrawal_credentials = (
        spec.BLS_WITHDRAWAL_PREFIX + b"\x00" * 31
    )
    voluntary_exit_request = prepare_voluntary_exit_request(spec, state, validator_index)

    yield from run_voluntary_exit_request_processing(spec, state, voluntary_exit_request)

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_phases([PQ])
@spec_state_test
def test_voluntary_exit_request_unknown_pubkey(spec, state):
    advance_past_shard_committee_period(spec, state)
    validator_pubkeys = [validator.pubkey for validator in state.validators]
    unknown_pubkey = next(pubkey for pubkey in xmss_pubkeys if pubkey not in validator_pubkeys)
    voluntary_exit_request = spec.VoluntaryExitRequest(pubkey=unknown_pubkey)

    yield from run_voluntary_exit_request_processing(
        spec, state, voluntary_exit_request, valid=False
    )


@with_phases([PQ])
@spec_state_test
def test_voluntary_exit_request_inactive_validator(spec, state):
    advance_past_shard_committee_period(spec, state)
    validator_index = 0
    state.validators[validator_index].activation_epoch = spec.get_current_epoch(state) + 1
    voluntary_exit_request = prepare_voluntary_exit_request(spec, state, validator_index)

    yield from run_voluntary_exit_request_processing(
        spec, state, voluntary_exit_request, valid=False
    )


@with_phases([PQ])
@spec_state_test
def test_voluntary_exit_request_already_exiting(spec, state):
    advance_past_shard_committee_period(spec, state)
    validator_index = 0
    spec.initiate_validator_exit(state, validator_index)
    voluntary_exit_request = prepare_voluntary_exit_request(spec, state, validator_index)

    yield from run_voluntary_exit_request_processing(
        spec, state, voluntary_exit_request, valid=False
    )


@with_phases([PQ])
@spec_state_test
def test_voluntary_exit_request_not_active_long_enough(spec, state):
    validator_index = 0
    voluntary_exit_request = prepare_voluntary_exit_request(spec, state, validator_index)

    yield from run_voluntary_exit_request_processing(
        spec, state, voluntary_exit_request, valid=False
    )


@with_phases([PQ])
@spec_state_test
def test_voluntary_exit_request_pending_withdrawal(spec, state):
    advance_past_shard_committee_period(spec, state)
    validator_index = 0
    state.pending_partial_withdrawals.append(
        spec.PendingPartialWithdrawal(
            validator_index=validator_index,
            amount=spec.EFFECTIVE_BALANCE_INCREMENT,
            withdrawable_epoch=spec.get_current_epoch(state),
        )
    )
    voluntary_exit_request = prepare_voluntary_exit_request(spec, state, validator_index)

    yield from run_voluntary_exit_request_processing(
        spec, state, voluntary_exit_request, valid=False
    )
