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
    process_proposer_attestation_rewards,
)


def expected_deposit_count(state: BeaconState) -> int:
    return min(
        spec.MAX_DEPOSITS,
        state.latest_eth1_data.deposit_count - state.deposit_index
    )


def process_operation_type(state: BeaconState,
                           operations: List[Any],
                           max_operations: int,
                           tx_fn: Callable[[BeaconState, Any], None]) -> None:
    assert len(operations) <= max_operations
    for operation in operations:
        tx_fn(state, operation)


def process_operations(state: BeaconState, block: BeaconBlock) -> None:
    process_operation_type(
        state,
        block.body.proposer_slashings,
        spec.MAX_PROPOSER_SLASHINGS,
        spec.process_proposer_slashing,
    )

    process_operation_type(
        state,
        block.body.attester_slashings,
        spec.MAX_ATTESTER_SLASHINGS,
        spec.process_attester_slashing,
    )

    process_operation_type(
        state,
        block.body.attestations,
        spec.MAX_ATTESTATIONS,
        spec.process_attestation,
    )
    process_proposer_attestation_rewards(state)

    assert len(block.body.deposits) == expected_deposit_count(state)
    process_operation_type(
        state,
        block.body.deposits,
        spec.MAX_DEPOSITS,
        spec.process_deposit,
    )

    process_operation_type(
        state,
        block.body.voluntary_exits,
        spec.MAX_VOLUNTARY_EXITS,
        spec.process_voluntary_exit,
    )

    assert len(block.body.transfers) == len(set(block.body.transfers))
    process_operation_type(
        state,
        block.body.transfers,
        spec.MAX_TRANSFERS,
        spec.process_transfer,
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
    spec.update_justification_and_finalization(state)
    spec.process_crosslinks(state)
    spec.apply_rewards(state)
    spec.process_balance_driven_status_transitions(state)
    spec.update_registry(state)
    spec.process_slashings(state)
    spec.finish_epoch_update(state)


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
