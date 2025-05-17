from eth2spec.test.context import (
    always_bls,
    scaled_churn_balances_min_churn_limit,
    single_phase,
    spec_state_test,
    spec_test,
    with_all_phases,
    with_custom_state,
    with_presets,
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.keys import pubkey_to_privkey
from eth2spec.test.helpers.voluntary_exits import (
    run_voluntary_exit_processing,
    sign_voluntary_exit,
)


@with_all_phases
@spec_state_test
def test_basic(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index),
        privkey,
    )

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    assert state.validators[validator_index].exit_epoch == spec.compute_activation_exit_epoch(
        current_epoch
    )


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_signature(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]

    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, 12345)

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit, valid=False)


def run_test_success_exit_queue(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)

    # exit `MAX_EXITS_PER_EPOCH`
    initial_indices = spec.get_active_validator_indices(state, current_epoch)[
        : spec.get_validator_churn_limit(state)
    ]

    # Prepare a bunch of exits, based on the current state
    exit_queue = []
    for index in initial_indices:
        privkey = pubkey_to_privkey[state.validators[index].pubkey]

        signed_voluntary_exit = sign_voluntary_exit(
            spec, state, spec.VoluntaryExit(epoch=current_epoch, validator_index=index), privkey
        )

        exit_queue.append(signed_voluntary_exit)

    # Now run all the exits
    for voluntary_exit in exit_queue:
        # the function yields data, but we are just interested in running it here, ignore yields.
        for _ in run_voluntary_exit_processing(spec, state, voluntary_exit):
            continue

    # exit an additional validator
    validator_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index),
        privkey,
    )

    # This is the interesting part of the test: on a pre-state with a full exit queue,
    #  when processing an additional exit, it results in an exit in a later epoch
    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    for index in initial_indices:
        assert (
            state.validators[validator_index].exit_epoch == state.validators[index].exit_epoch + 1
        )


@with_all_phases
@spec_state_test
def test_success_exit_queue__min_churn(spec, state):
    yield from run_test_success_exit_queue(spec, state)


@with_all_phases
@with_presets(
    [MINIMAL],
    reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated",
)
@spec_test
@with_custom_state(
    balances_fn=scaled_churn_balances_min_churn_limit,
    threshold_fn=lambda spec: spec.config.EJECTION_BALANCE,
)
@single_phase
def test_success_exit_queue__scaled_churn(spec, state):
    churn_limit = spec.get_validator_churn_limit(state)
    assert churn_limit > spec.config.MIN_PER_EPOCH_CHURN_LIMIT
    yield from run_test_success_exit_queue(spec, state)


@with_all_phases
@spec_state_test
def test_default_exit_epoch_subsequent_exit(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index),
        privkey,
    )

    # Exit one validator prior to this new one
    exited_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    state.validators[exited_index].exit_epoch = current_epoch - 1

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    assert state.validators[validator_index].exit_epoch == spec.compute_activation_exit_epoch(
        current_epoch
    )


@with_all_phases
@spec_state_test
def test_invalid_validator_exit_in_future(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch + 1,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_validator_incorrect_validator_index(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=len(state.validators),
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_validator_not_active(spec, state):
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    state.validators[validator_index].activation_epoch = spec.FAR_FUTURE_EPOCH

    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index),
        privkey,
    )

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_validator_already_exited(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow validator able to exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    # but validator already has exited
    state.validators[validator_index].exit_epoch = current_epoch + 2

    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index),
        privkey,
    )

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_validator_not_active_long_enough(spec, state):
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index),
        privkey,
    )

    assert (
        current_epoch - state.validators[validator_index].activation_epoch
        < spec.config.SHARD_COMMITTEE_PERIOD
    )

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit, valid=False)
