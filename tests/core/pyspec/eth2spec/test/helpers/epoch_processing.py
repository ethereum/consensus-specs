
from eth2spec.test.helpers.forks import (
    is_post_altair,
    is_post_capella,
)


def get_process_calls(spec):
    # unrecognized processing functions will be ignored.
    # This sums up the aggregate of processing functions of all phases.
    # Note: make sure to explicitly remove/override a processing function in later phases,
    # or the old function will stick around.
    return [
        'process_justification_and_finalization',
        'process_inactivity_updates',  # altair
        'process_rewards_and_penalties',
        'process_registry_updates',
        'process_reveal_deadlines',  # custody game
        'process_challenge_deadlines',  # custody game
        'process_slashings',
        'process_pending_header.',  # sharding
        'charge_confirmed_header_fees',  # sharding
        'reset_pending_headers',  # sharding
        'process_eth1_data_reset',
        'process_pending_deposits',  # electra
        'process_pending_consolidations',  # electra
        'process_effective_balance_updates',
        'process_slashings_reset',
        'process_randao_mixes_reset',
        # Capella replaced `process_historical_roots_update` with `process_historical_summaries_update`
        'process_historical_summaries_update' if is_post_capella(spec) else (
            'process_historical_roots_update'
        ),
        # Altair replaced `process_participation_record_updates` with `process_participation_flag_updates`
        'process_participation_flag_updates' if is_post_altair(spec) else (
            'process_participation_record_updates'
        ),
        'process_sync_committee_updates',  # altair
        # TODO: add sharding processing functions when spec stabilizes.
    ]


def run_epoch_processing_to(spec, state, process_name: str, disable_slots_processing=False):
    """
    Processes to the next epoch transition, up to, but not including, the sub-transition named ``process_name``
    """
    if not disable_slots_processing:
        run_process_slots_up_to_epoch_boundary(spec, state)

    # process components of epoch transition before final-updates
    for name in get_process_calls(spec):
        if name == process_name:
            break
        # only run when present. Later phases introduce more to the epoch-processing.
        if hasattr(spec, name):
            getattr(spec, name)(state)


def run_process_slots_up_to_epoch_boundary(spec, state):
    """
    Processes slots until the next epoch transition
    """
    slot = state.slot + (spec.SLOTS_PER_EPOCH - state.slot %
                         spec.SLOTS_PER_EPOCH)

    # transition state to slot before epoch state transition
    if state.slot < slot - 1:
        spec.process_slots(state, slot - 1)

    # start transitioning, do one slot update before the epoch itself.
    spec.process_slot(state)


def run_epoch_processing_from(spec, state, process_name: str):
    """
    Processes to the next epoch transition, fom, but not including, the sub-transition named ``process_name``
    """
    assert (state.slot + 1) % spec.SLOTS_PER_EPOCH == 0

    procesing = False
    for name in get_process_calls(spec):
        if name == process_name:
            procesing = True
            continue
        # only run when present. Later phases introduce more to the epoch-processing.
        if procesing and hasattr(spec, name):
            getattr(spec, name)(state)


def run_epoch_processing_with(spec, state, process_name: str):
    """
    Processes to the next epoch transition, up to and including the sub-transition named ``process_name``
      - pre-state ('pre'), state before calling ``process_name``
      - post-state ('post'), state after calling ``process_name``
      - pre-full-state ('pre_full'), state before epoch transition
      - post-full-state ('post_full'), state after epoch transition
    The state passed by reference will be modified to be the ``process_name``post state.
    """
    run_process_slots_up_to_epoch_boundary(spec, state)
    yield "pre_full", state
    run_epoch_processing_to(spec, state, process_name,
                            disable_slots_processing=True)
    yield 'pre', state
    getattr(spec, process_name)(state)
    yield 'post', state
    continue_state = state.copy()
    run_epoch_processing_from(spec, continue_state, process_name)
    yield 'post_full', continue_state
