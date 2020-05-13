
process_calls = [
    'process_justification_and_finalization',
    'process_rewards_and_penalties',
    'process_registry_updates',
    'process_reveal_deadlines',
    'process_challenge_deadlines',
    'process_slashings',
    'process_final_updates',
    'after_process_final_updates',
]


def run_epoch_processing_to(spec, state, process_name: str):
    """
    Processes to the next epoch transition, up to, but not including, the sub-transition named ``process_name``
    """
    slot = state.slot + (spec.SLOTS_PER_EPOCH - state.slot % spec.SLOTS_PER_EPOCH)

    # transition state to slot before epoch state transition
    if state.slot < slot - 1:
        spec.process_slots(state, slot - 1)

    # start transitioning, do one slot update before the epoch itself.
    spec.process_slot(state)

    # process components of epoch transition before final-updates
    for name in process_calls:
        if name == process_name:
            break
        # only run when present. Later phases introduce more to the epoch-processing.
        if hasattr(spec, name):
            getattr(spec, name)(state)


def run_epoch_processing_with(spec, state, process_name: str):
    """
    Processes to the next epoch transition, up to and including the sub-transition named ``process_name``
      - pre-state ('pre'), state before calling ``process_name``
      - post-state ('post'), state after calling ``process_name``
    """
    run_epoch_processing_to(spec, state, process_name)
    yield 'pre', state
    getattr(spec, process_name)(state)
    yield 'post', state
