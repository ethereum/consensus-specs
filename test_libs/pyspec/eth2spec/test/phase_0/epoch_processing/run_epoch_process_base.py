
process_calls = [
    'process_justification_and_finalization',
    'process_crosslinks',
    'process_rewards_and_penalties',
    'process_registry_updates',
    'process_reveal_deadlines',
    'process_challenge_deadlines',
    'process_slashings',
    'process_final_updates',
    'after_process_final_updates',
]


def run_epoch_processing_to(spec, state, process_name: str, exclusive=False):
    """
    Run the epoch processing functions up to ``process_name``.
    If ``exclusive`` is True, the process itself will not be ran.
    If ``exclusive`` is False (default), this function yields:
      - pre-state ('pre'), state before calling ``process_name``
      - post-state ('post'), state after calling ``process_name``
    """
    slot = state.slot + (spec.SLOTS_PER_EPOCH - state.slot % spec.SLOTS_PER_EPOCH)

    # transition state to slot before epoch state transition
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

    if not exclusive:
        yield 'pre', state
        getattr(spec, process_name)(state)
        yield 'post', state
