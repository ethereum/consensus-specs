from . import spec


from typing import (
    Any,
    Callable,
    List
)

from .spec import (
    BeaconState,
    BeaconBlock,
    Slot,
)


def process_block(state: BeaconState, block: BeaconBlock, verify_state_root) -> None:
    spec.process_block_header(state, block)
    spec.process_randao(state, block)
    spec.process_eth1_data(state, block)
    spec.process_operations(state, block.body)
    if verify_state_root:
        spec.verify_block_state_root(state, block)


def process_epoch_transition(state: BeaconState) -> None:
    spec.process_justification_and_finalization(state)
    spec.process_crosslinks(state)
    spec.process_rewards_and_penalties(state)
    spec.process_registry_updates(state)
    spec.process_slashings(state)
    spec.process_final_updates(state)


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
