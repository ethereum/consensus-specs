from eth2spec.test.helpers.block import build_empty_block_for_next_slot, sign_block
from eth2spec.test.helpers.state import next_epoch, state_transition_and_sign_block
from eth2spec.test.context import spec_state_test, with_all_phases


def run_process_registry_updates(spec, state, valid=True):
    """
    Run ``process_crosslinks``, yielding:
      - pre-state ('pre')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    # transition state to slot before state transition
    slot = state.slot + (spec.SLOTS_PER_EPOCH - state.slot % spec.SLOTS_PER_EPOCH) - 1
    block = build_empty_block_for_next_slot(spec, state)
    block.slot = slot
    sign_block(spec, state, block)
    state_transition_and_sign_block(spec, state, block)

    # cache state before epoch transition
    spec.process_slot(state)

    # process components of epoch transition before registry update
    spec.process_justification_and_finalization(state)
    spec.process_crosslinks(state)
    spec.process_rewards_and_penalties(state)

    yield 'pre', state
    spec.process_registry_updates(state)
    yield 'post', state


@with_all_phases
@spec_state_test
def test_activation(spec, state):
    index = 0
    assert spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))

    # Mock a new deposit
    state.validators[index].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH
    state.validators[index].activation_epoch = spec.FAR_FUTURE_EPOCH
    state.validators[index].effective_balance = spec.MAX_EFFECTIVE_BALANCE
    assert not spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))

    for _ in range(spec.ACTIVATION_EXIT_DELAY + 1):
        next_epoch(spec, state)

    yield from run_process_registry_updates(spec, state)

    assert state.validators[index].activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
    assert state.validators[index].activation_epoch != spec.FAR_FUTURE_EPOCH
    assert spec.is_active_validator(
        state.validators[index],
        spec.get_current_epoch(state),
    )


@with_all_phases
@spec_state_test
def test_ejection(spec, state):
    index = 0
    assert spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))
    assert state.validators[index].exit_epoch == spec.FAR_FUTURE_EPOCH

    # Mock an ejection
    state.validators[index].effective_balance = spec.EJECTION_BALANCE

    for _ in range(spec.ACTIVATION_EXIT_DELAY + 1):
        next_epoch(spec, state)

    yield from run_process_registry_updates(spec, state)

    assert state.validators[index].exit_epoch != spec.FAR_FUTURE_EPOCH
    assert not spec.is_active_validator(
        state.validators[index],
        spec.get_current_epoch(state),
    )
