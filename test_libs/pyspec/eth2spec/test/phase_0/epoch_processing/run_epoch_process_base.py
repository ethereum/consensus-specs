from eth2spec.test.helpers.block import build_empty_block_for_next_slot, sign_block
from eth2spec.test.helpers.state import state_transition_and_sign_block


process_calls = (
    'process_justification_and_finalization'
    'process_crosslinks'
    'process_rewards_and_penalties'
    'process_registry_updates'
    'process_reveal_deadlines'
    'process_challenge_deadlines'
    'process_slashings'
    'process_final_updates'
    'after_process_final_updates'
)


def run_epoch_processing_to(spec, state, process_name: str):
    """
    Run the epoch processing functions up to ``process_name`` (incl.), yielding:
      - pre-state ('pre'), state before calling ``process_name``
      - post-state ('post'), state after calling ``process_name``
    """
    # transition state to slot before state transition
    slot = state.slot + (spec.SLOTS_PER_EPOCH - state.slot % spec.SLOTS_PER_EPOCH) - 1
    block = build_empty_block_for_next_slot(spec, state)
    block.slot = slot
    sign_block(spec, state, block)
    state_transition_and_sign_block(spec, state, block)

    # cache state before epoch transition
    spec.process_slot(state)

    # process components of epoch transition before final-updates
    for name in process_calls:
        if name == process_name:
            break
        # only run when present. Later phases introduce more to the epoch-processing.
        if hasattr(spec, name):
            getattr(spec, name)(state)

    yield 'pre', state
    getattr(spec, process_name)(state)
    yield 'post', state
