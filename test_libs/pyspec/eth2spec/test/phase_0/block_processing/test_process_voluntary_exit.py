from eth2spec.test.context import spec_state_test, expect_assertion_error, always_bls, with_all_phases
from eth2spec.test.helpers.keys import pubkey_to_privkey
from eth2spec.test.helpers.voluntary_exits import build_voluntary_exit, sign_voluntary_exit


def run_voluntary_exit_processing(spec, state, voluntary_exit, valid=True):
    """
    Run ``process_voluntary_exit``, yielding:
      - pre-state ('pre')
      - voluntary_exit ('voluntary_exit')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    validator_index = voluntary_exit.validator_index

    yield 'pre', state
    yield 'voluntary_exit', voluntary_exit

    if not valid:
        expect_assertion_error(lambda: spec.process_voluntary_exit(state, voluntary_exit))
        yield 'post', None
        return

    pre_exit_epoch = state.validators[validator_index].exit_epoch

    spec.process_voluntary_exit(state, voluntary_exit)

    yield 'post', state

    assert pre_exit_epoch == spec.FAR_FUTURE_EPOCH
    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_all_phases
@spec_state_test
def test_success(spec, state):
    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    voluntary_exit = build_voluntary_exit(spec, state, current_epoch, validator_index, privkey, signed=True)

    yield from run_voluntary_exit_processing(spec, state, voluntary_exit)


@with_all_phases
@always_bls
@spec_state_test
def test_invalid_signature(spec, state):
    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    voluntary_exit = build_voluntary_exit(spec, state, current_epoch, validator_index, privkey)

    yield from run_voluntary_exit_processing(spec, state, voluntary_exit, False)


@with_all_phases
@spec_state_test
def test_success_exit_queue(spec, state):
    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)

    # exit `MAX_EXITS_PER_EPOCH`
    initial_indices = spec.get_active_validator_indices(state, current_epoch)[:spec.get_churn_limit(state)]

    # Prepare a bunch of exits, based on the current state
    exit_queue = []
    for index in initial_indices:
        privkey = pubkey_to_privkey[state.validators[index].pubkey]
        exit_queue.append(build_voluntary_exit(
            spec,
            state,
            current_epoch,
            index,
            privkey,
            signed=True,
        ))

    # Now run all the exits
    for voluntary_exit in exit_queue:
        # the function yields data, but we are just interested in running it here, ignore yields.
        for _ in run_voluntary_exit_processing(spec, state, voluntary_exit):
            continue

    # exit an additional validator
    validator_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]
    voluntary_exit = build_voluntary_exit(
        spec,
        state,
        current_epoch,
        validator_index,
        privkey,
        signed=True,
    )

    # This is the interesting part of the test: on a pre-state with a full exit queue,
    #  when processing an additional exit, it results in an exit in a later epoch
    yield from run_voluntary_exit_processing(spec, state, voluntary_exit)

    assert (
        state.validators[validator_index].exit_epoch ==
        state.validators[initial_indices[0]].exit_epoch + 1
    )


@with_all_phases
@spec_state_test
def test_validator_exit_in_future(spec, state):
    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    voluntary_exit = build_voluntary_exit(
        spec,
        state,
        current_epoch,
        validator_index,
        privkey,
        signed=False,
    )
    voluntary_exit.epoch += 1
    sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    yield from run_voluntary_exit_processing(spec, state, voluntary_exit, False)


@with_all_phases
@spec_state_test
def test_validator_invalid_validator_index(spec, state):
    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    voluntary_exit = build_voluntary_exit(
        spec,
        state,
        current_epoch,
        validator_index,
        privkey,
        signed=False,
    )
    voluntary_exit.validator_index = len(state.validators)
    sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    yield from run_voluntary_exit_processing(spec, state, voluntary_exit, False)


@with_all_phases
@spec_state_test
def test_validator_not_active(spec, state):
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    state.validators[validator_index].activation_epoch = spec.FAR_FUTURE_EPOCH

    # build and test voluntary exit
    voluntary_exit = build_voluntary_exit(
        spec,
        state,
        current_epoch,
        validator_index,
        privkey,
        signed=True,
    )

    yield from run_voluntary_exit_processing(spec, state, voluntary_exit, False)


@with_all_phases
@spec_state_test
def test_validator_already_exited(spec, state):
    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow validator able to exit
    state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    # but validator already has exited
    state.validators[validator_index].exit_epoch = current_epoch + 2

    voluntary_exit = build_voluntary_exit(
        spec,
        state,
        current_epoch,
        validator_index,
        privkey,
        signed=True,
    )

    yield from run_voluntary_exit_processing(spec, state, voluntary_exit, False)


@with_all_phases
@spec_state_test
def test_validator_not_active_long_enough(spec, state):
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    voluntary_exit = build_voluntary_exit(
        spec,
        state,
        current_epoch,
        validator_index,
        privkey,
        signed=True,
    )

    assert (
        current_epoch - state.validators[validator_index].activation_epoch <
        spec.PERSISTENT_COMMITTEE_PERIOD
    )

    yield from run_voluntary_exit_processing(spec, state, voluntary_exit, False)
