from . import spec

from .spec import (
    BeaconState,
    BeaconBlock,
    Slot,
)

from eth2spec.phase0.state_transition import (
    process_operation_type,
    process_operations as process_operations_phase0,
)


def process_operations(state: BeaconState, block: BeaconBlock) -> None:
    process_operations_phase0(state, block)

    process_operation_type(
        state,
        block.body.custody_key_reveals,
        spec.MAX_CUSTODY_KEY_REVEALS,
        spec.process_custody_key_reveal,
    )

    process_operation_type(
        state,
        block.body.early_derived_secret_reveals,
        spec.MAX_EARLY_DERIVED_SECRET_REVEALS,
        spec.process_early_derived_secret_reveal,
    )


def process_block(state: BeaconState,
                  block: BeaconBlock,
                  verify_state_root: bool=False) -> None:
    spec.process_block_header(state, block)
    spec.process_randao(state, block)
    spec.process_eth1_data(state, block)

    process_operations(state, block)
    if verify_state_root:
        spec.verify_block_state_root(state, block)


def process_epoch_transition(state: BeaconState) -> None:
    spec.process_justification_and_finalization(state)
    spec.process_crosslinks(state)
    # TODO: Eligible
    spec.process_rewards_and_penalties(state)
    spec.process_registry_updates(state)
    spec.process_reveal_deadlines(state)
    spec.process_challenge_deadlines(state)
    spec.process_slashings(state)
    spec.process_final_updates(state)
    spec.after_process_final_updates(state)


def state_transition_to(state: BeaconState, up_to: Slot) -> BeaconState:
    while state.slot < up_to:
        spec.cache_state(state)
        if (state.slot + 1) % spec.SLOTS_PER_EPOCH == 0:
            process_epoch_transition(state)
        spec.advance_slot(state)


def state_transition(state: BeaconState,
                     block: BeaconBlock,
                     verify_state_root: bool=False) -> BeaconState:
    state_transition_to(state, block.slot)
    process_block(state, block, verify_state_root)
