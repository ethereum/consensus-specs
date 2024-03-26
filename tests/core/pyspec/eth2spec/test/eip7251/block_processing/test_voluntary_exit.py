from eth2spec.test.helpers.constants import (MINIMAL, MAINNET)
from eth2spec.test.context import (
    spec_state_test,
    with_eip7251_and_later,
    with_presets, 
    always_bls,
    spec_test, single_phase,
    with_custom_state,
    scaled_churn_balances_min_churn_limit,
)
from eth2spec.test.helpers.keys import pubkey_to_privkey
from eth2spec.test.helpers.voluntary_exits import (
    run_voluntary_exit_processing,
    sign_voluntary_exit,
)
#  ********************
#  * EXIT QUEUE TESTS *
#  ********************

@with_eip7251_and_later
@spec_state_test
def test_min_balance_exit(spec, state):
    # This state has 64 validators each with 32 ETH
    expected_exit_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    churn_limit = spec.get_activation_exit_churn_limit(state)
    # Set the balance to consume equal to churn limit
    state.exit_balance_to_consume = churn_limit

    yield "pre", state
    # Exit validators, all which fit in the churn limit
    spec.initiate_validator_exit(state, 0)
    yield "post", state

    # Check exit queue churn is set
    assert state.exit_balance_to_consume == churn_limit  - spec.MIN_ACTIVATION_BALANCE
    # Check exit epoch
    assert state.validators[0].exit_epoch == expected_exit_epoch


@with_eip7251_and_later
@spec_state_test
def test_min_balance_exits_up_to_churn(spec, state):
    # This state has 64 validators each with 32 ETH
    single_validator_balance = spec.MIN_ACTIVATION_BALANCE
    expected_exit_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    churn_limit = spec.get_activation_exit_churn_limit(state)
    # Set the balance to consume equal to churn limit
    state.exit_balance_to_consume = churn_limit

    yield "pre", state
    # Exit validators, all which fit in the churn limit
    for i in range(churn_limit // spec.MIN_ACTIVATION_BALANCE):
        validator_index = i
        spec.initiate_validator_exit(state, validator_index)
        yield f"post{i}", state
        # Check exit queue churn is set
        assert state.exit_balance_to_consume == churn_limit  - single_validator_balance * (i + 1)
        # Check exit epoch
        assert state.validators[validator_index].exit_epoch == expected_exit_epoch
    yield "post", state

@with_eip7251_and_later
@spec_state_test
def test_min_balance_exits_above_churn(spec, state):
    # This state has 64 validators each with 32 ETH
    single_validator_balance = spec.MIN_ACTIVATION_BALANCE
    expected_exit_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    churn_limit = spec.get_activation_exit_churn_limit(state)
    # Set the balance to consume equal to churn limit
    state.exit_balance_to_consume = churn_limit

    yield "pre", state
    # Exit validators, all which fit in the churn limit
    for i in range(churn_limit // spec.MIN_ACTIVATION_BALANCE):
        validator_index = i
        spec.initiate_validator_exit(state, validator_index)
        # Check exit queue churn is set
        assert state.exit_balance_to_consume == churn_limit  - single_validator_balance * (i + 1)
        # Check exit epoch
        assert state.validators[validator_index].exit_epoch == expected_exit_epoch

    # Exit balance has been fully consumed
    assert state.exit_balance_to_consume == 0

    # Exit an additional validator, doesn't fit in the churn limit, so exit
    # epoch is incremented
    validator_index = churn_limit // spec.MIN_ACTIVATION_BALANCE
    spec.initiate_validator_exit(state, validator_index)

    yield "post", state
    # Check exit epoch
    assert state.validators[validator_index].exit_epoch == expected_exit_epoch + 1
    # Check exit balance to consume is set
    assert state.exit_balance_to_consume == churn_limit - single_validator_balance



# @with_eip7251_and_later
# @spec_state_test
# def test_exit_balance_to_consume_large_validator(spec, state):
#     # Set 0th validator effective balance to 2048 ETH
#     state.validators[0].effective_balance = spec.MAX_EFFECTIVE_BALANCE_EIP7251 
#     churn_limit = spec.get_validator_churn_limit(state)
#     expected_exit_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
#     expected_exit_epoch += spec.MAX_EFFECTIVE_BALANCE_EIP7251 // churn_limit

#     validator_index = 0
#     spec.initiate_validator_exit(state, validator_index)
#     # Check exit epoch
#     assert state.validators[validator_index].exit_epoch == expected_exit_epoch
#     # Check exit_balance_to_consume
#     assert state.exit_balance_to_consume == churn_limit - (spec.MAX_EFFECTIVE_BALANCE_EIP7251 % churn_limit)
#     # Check earliest_exit_epoch
#     assert state.earliest_exit_epoch == expected_exit_epoch

@with_eip7251_and_later
@spec_state_test
@with_presets([MAINNET], "With CHURN_LIMIT_QUOTIENT=32, can't change validator balance without changing churn_limit")
def test_max_balance_exit(spec, state):
    churn_limit = spec.get_activation_exit_churn_limit(state)
    assert churn_limit == spec.MIN_ACTIVATION_BALANCE * spec.config.MIN_PER_EPOCH_CHURN_LIMIT

    # Set 0th validator effective balance to 2048 ETH
    state.validators[0].effective_balance = spec.MAX_EFFECTIVE_BALANCE_EIP7251
    yield 'pre', state

    expected_exit_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    # Validator consumes exit churn for 16 epochs, exits at the 17th one
    expected_exit_epoch += (spec.MAX_EFFECTIVE_BALANCE_EIP7251 // churn_limit)

    validator_index = 0
    spec.initiate_validator_exit(state, validator_index)
    yield 'post', state
    # Check exit epoch
    assert state.validators[validator_index].exit_epoch == expected_exit_epoch
    # Check exit_balance_to_consume
    assert state.exit_balance_to_consume == churn_limit
    # Check earliest_exit_epoch
    assert state.earliest_exit_epoch == expected_exit_epoch


@with_eip7251_and_later
@spec_state_test
@with_presets([MAINNET], "With CHURN_LIMIT_QUOTIENT=32, can't change validator balance without changing churn_limit")
def test_exit_with_balance_equal_to_churn_limit(spec, state):
    churn_limit = spec.get_activation_exit_churn_limit(state)

    # Set 0th validator effective balance to churn_limit
    state.validators[0].effective_balance = churn_limit
    yield 'pre', state

    validator_index = 0
    spec.initiate_validator_exit(state, validator_index)

    yield 'post', state
    # Validator consumes churn limit fully in the current epoch
    assert state.validators[validator_index].exit_epoch == spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    # Check exit_balance_to_consume
    assert state.exit_balance_to_consume == 0
    # Check earliest_exit_epoch
    assert state.earliest_exit_epoch == state.validators[validator_index].exit_epoch

@with_eip7251_and_later
@spec_state_test
@with_presets([MAINNET], "With CHURN_LIMIT_QUOTIENT=32, can't change validator balance without changing churn_limit")
def test_exit_churn_limit_balance_existing_churn_(spec, state):
    cl = spec.get_activation_exit_churn_limit(state)
    
    # set exit epoch to the first available one and set exit balance to consume to full churn limit
    state.earliest_exit_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    state.exit_balance_to_consume = cl
    # consume some churn in exit epoch
    state.exit_balance_to_consume -= 1000000000

    # Set 0th validator effective balance to the churn limit
    state.validators[0].effective_balance = cl

    yield 'pre', state

    # The existing 1 ETH churn will push an extra epoch
    expected_exit_epoch = state.earliest_exit_epoch + 1

    yield 'post', state
    validator_index = 0
    spec.initiate_validator_exit(state, validator_index)
    # Check exit epoch
    assert state.validators[validator_index].exit_epoch == expected_exit_epoch
    # Check balance consumed in exit epoch is the remainder 1 ETH
    assert state.exit_balance_to_consume == cl - 1000000000
    # check earliest exit epoch 
    assert expected_exit_epoch == state.earliest_exit_epoch


@with_eip7251_and_later
@spec_state_test
@with_presets([MAINNET], "With CHURN_LIMIT_QUOTIENT=32, can't change validator balance without changing churn_limit")
def test_multi_epoch_exit_existing_churn(spec, state):
    cl = spec.get_activation_exit_churn_limit(state)

    # set exit epoch to the first available one and set exit balance to consume to full churn limit
    state.earliest_exit_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    state.exit_balance_to_consume = cl
    # consume some churn in exit epoch
    state.exit_balance_to_consume -= 1000000000


    # Set 0th validator effective balance to 2x the churn limit
    state.validators[0].effective_balance = 2*cl

    yield 'pre', state
    # Two extra epochs will be necessary
    expected_exit_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state)) + 2

    validator_index = 0
    spec.initiate_validator_exit(state, validator_index)
    yield 'post', state
    # Check exit epoch
    assert state.validators[validator_index].exit_epoch == expected_exit_epoch
    # Check balance consumed in exit epoch is the remainder 1 ETH
    assert state.exit_balance_to_consume == cl - 1000000000
    # check earliest exit epoch 
    assert expected_exit_epoch == state.earliest_exit_epoch
    

### Repurposed from  phase0 voluntary exit tests, should disable the phase0 ones

def run_test_success_exit_queue(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    churn_limit = spec.get_activation_exit_churn_limit(state)
    # exit `MAX_EXITS_PER_EPOCH`
    max_exits = churn_limit // spec.MIN_ACTIVATION_BALANCE
    initial_indices = spec.get_active_validator_indices(state, current_epoch)[:max_exits]

    # Prepare a bunch of exits, based on the current state
    exit_queue = []
    for index in initial_indices:
        privkey = pubkey_to_privkey[state.validators[index].pubkey]

        signed_voluntary_exit = sign_voluntary_exit(
            spec, state, spec.VoluntaryExit(epoch=current_epoch, validator_index=index), privkey)

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
        spec, state, spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index), privkey)

    # This is the interesting part of the test: on a pre-state with a full exit queue,
    #  when processing an additional exit, it results in an exit in a later epoch
    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    for index in initial_indices:
        assert (
            state.validators[validator_index].exit_epoch ==
            state.validators[index].exit_epoch + 1
        )
    assert state.earliest_exit_epoch == state.validators[validator_index].exit_epoch
    consumed_churn = spec.MIN_ACTIVATION_BALANCE * (max_exits+1)
    assert state.exit_balance_to_consume ==  churn_limit - (consumed_churn % churn_limit)


@with_eip7251_and_later
@spec_state_test
def test_success_exit_queue__min_churn(spec, state):
    yield from run_test_success_exit_queue(spec, state)

@with_eip7251_and_later
@with_presets([MINIMAL],
              reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated")
@spec_test
@with_custom_state(balances_fn=scaled_churn_balances_min_churn_limit,
                   threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@single_phase
def test_success_exit_queue__scaled_churn(spec, state):
    churn_limit = spec.get_activation_exit_churn_limit(state)
    assert churn_limit > spec.config.MIN_PER_EPOCH_CHURN_LIMIT
    yield from run_test_success_exit_queue(spec, state)


#### After here no modifications were made, can just leave them in phase0 as is


@with_eip7251_and_later
@spec_state_test
def test_basic(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    signed_voluntary_exit = sign_voluntary_exit(
        spec, state, spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index), privkey)

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    assert state.validators[validator_index].exit_epoch == spec.compute_activation_exit_epoch(current_epoch)


@with_eip7251_and_later
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







@with_eip7251_and_later
@spec_state_test
def test_default_exit_epoch_subsequent_exit(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    signed_voluntary_exit = sign_voluntary_exit(
        spec, state, spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index), privkey)

    # Exit one validator prior to this new one
    exited_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    state.validators[exited_index].exit_epoch = current_epoch - 1

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    assert state.validators[validator_index].exit_epoch == spec.compute_activation_exit_epoch(current_epoch)


@with_eip7251_and_later
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


@with_eip7251_and_later
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


@with_eip7251_and_later
@spec_state_test
def test_invalid_validator_not_active(spec, state):
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    state.validators[validator_index].activation_epoch = spec.FAR_FUTURE_EPOCH

    signed_voluntary_exit = sign_voluntary_exit(
        spec, state, spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index), privkey)

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit, valid=False)


@with_eip7251_and_later
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
        spec, state, spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index), privkey)

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit, valid=False)


@with_eip7251_and_later
@spec_state_test
def test_invalid_validator_not_active_long_enough(spec, state):
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    signed_voluntary_exit = sign_voluntary_exit(
        spec, state, spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index), privkey)

    assert (
        current_epoch - state.validators[validator_index].activation_epoch <
        spec.config.SHARD_COMMITTEE_PERIOD
    )

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit, valid=False)
