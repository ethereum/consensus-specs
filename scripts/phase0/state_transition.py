

def process_transaction_type(state: BeaconState,
                             transactions: List[Any],
                             max_transactions: int,
                             tx_fn: Callable[[BeaconState, Any], None]) -> None:
    assert len(transactions) <= max_transactions
    for transaction in transactions:
        tx_fn(state, transaction)


def process_transactions(state: BeaconState, block: BeaconBlock) -> None:
    process_transaction_type(
        state,
        block.body.proposer_slashings,
        MAX_PROPOSER_SLASHINGS,
        process_proposer_slashing,
    )
    process_transaction_type(
        state,
        block.body.attester_slashings,
        MAX_ATTESTER_SLASHINGS,
        process_attester_slashing,
    )
    process_transaction_type(
        state,
        block.body.attestations,
        MAX_ATTESTATIONS,
        process_attestation,
    )
    process_transaction_type(
        state,
        block.body.deposits,
        MAX_DEPOSITS,
        process_deposit,
    )
    process_transaction_type(
        state,
        block.body.voluntary_exits,
        MAX_VOLUNTARY_EXITS,
        process_voluntary_exit,
    )
    assert len(block.body.transfers) == len(set(block.body.transfers))
    process_transaction_type(
        state,
        block.body.transfers,
        MAX_TRANSFERS,
        process_transfer,
    )


def process_block(state: BeaconState,
                  block: BeaconBlock,
                  verify_state_root: bool=False) -> None:
    process_block_header(state, block)
    process_randao(state, block)
    process_eth1_data(state, block)
    process_transactions(state, block)
    if verify_state_root:
        verify_block_state_root(state, block)


def process_epoch_transition(state: BeaconState) -> None:
    update_justification_and_finalization(state)
    process_crosslinks(state)
    maybe_reset_eth1_period(state)
    apply_rewards(state)
    process_ejections(state)
    update_registry_and_shuffling_data(state)
    process_slashings(state)
    process_exit_queue(state)
    finish_epoch_update(state)


def state_transition(state: BeaconState,
                     block: BeaconBlock,
                     verify_state_root: bool=False) -> BeaconState:
    while state.slot < block.slot:
        cache_state(state)
        if (state.slot + 1) % SLOTS_PER_EPOCH == 0:
            process_epoch_transition(state)
        advance_slot(state)
        if block.slot == state.slot:
            process_block(state, block)
