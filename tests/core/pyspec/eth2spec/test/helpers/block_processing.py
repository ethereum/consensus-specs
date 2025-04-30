def for_ops(state, operations, fn) -> None:
    for operation in operations:
        fn(state, operation)


def get_process_calls(spec):
    return {
        # PHASE0
        "process_block_header": lambda state, block: spec.process_block_header(state, block),
        "process_randao": lambda state, block: spec.process_randao(state, block.body),
        "process_eth1_data": lambda state, block: spec.process_eth1_data(state, block.body),
        "process_proposer_slashing": lambda state, block: for_ops(
            state, block.body.proposer_slashings, spec.process_proposer_slashing
        ),
        "process_attester_slashing": lambda state, block: for_ops(
            state, block.body.attester_slashings, spec.process_attester_slashing
        ),
        "process_shard_header": lambda state, block: for_ops(
            state, block.body.shard_headers, spec.process_shard_header
        ),
        "process_attestation": lambda state, block: for_ops(
            state, block.body.attestations, spec.process_attestation
        ),
        "process_deposit": lambda state, block: for_ops(
            state, block.body.deposits, spec.process_deposit
        ),
        "process_voluntary_exit": lambda state, block: for_ops(
            state, block.body.voluntary_exits, spec.process_voluntary_exit
        ),
        # Altair
        "process_sync_aggregate": lambda state, block: spec.process_sync_aggregate(
            state, block.body.sync_aggregate
        ),
        # Bellatrix
        "process_application_payload": lambda state, block: spec.process_application_payload(
            state, block.body
        ),
        # Custody Game
        "process_custody_game_operations": lambda state, block: spec.process_custody_game_operations(
            state, block.body
        ),
    }


def run_block_processing_to(spec, state, block, process_name: str):
    """
    Processes to the block transition, up to, but not including, the sub-transition named ``process_name``.
    Returns a Callable[[state, block], None] for the remaining ``process_name`` transition.

    Tests should create full blocks to ensure a valid state transition, even if the operation itself is isolated.
    (e.g. latest_header in the beacon state is up-to-date in a sync-committee test).

    A test prepares a pre-state by calling this function, output the pre-state,
     and it can then proceed to run the returned callable, and output a post-state.
    """
    # transition state to slot before block state transition
    if state.slot < block.slot:
        spec.process_slots(state, block.slot)

    # process components of block transition
    for name, call in get_process_calls(spec).items():
        if name == process_name:
            return call
        # only run when present. Later phases introduce more to the block-processing.
        if hasattr(spec, name):
            call(state, block)
