# Electra -- The Beacon Chain

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Containers](#containers)
  - [New containers](#new-containers)
    - [`SyncData`](#syncdata)
  - [Extended containers](#extended-containers)
    - [`BeaconState`](#beaconstate)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_sync_committee_updates`](#modified-process_sync_committee_updates)
  - [Block processing](#block-processing)
    - [New `process_best_sync_data`](#new-process_best_sync_data)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Containers

### New containers

#### `SyncData`

```python
class SyncData(Container):
    # Sync committee aggregate signature
    sync_aggregate: SyncAggregate
    # Slot at which the aggregate signature was created
    signature_slot: Slot
```

### Extended containers

#### `BeaconState`

```python
class BeaconState(Container):
    # Versioning
    genesis_time: uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    # History
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]  # Frozen in Capella, replaced by historical_summaries
    # Eth1
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH]
    eth1_deposit_index: uint64
    # Registry
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    # Randomness
    randao_mixes: Vector[Bytes32, EPOCHS_PER_HISTORICAL_VECTOR]
    # Slashings
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]  # Per-epoch sums of slashed effective balances
    # Participation
    previous_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    current_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    # Inactivity
    inactivity_scores: List[uint64, VALIDATOR_REGISTRY_LIMIT]
    # Sync
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # Execution
    latest_execution_payload_header: ExecutionPayloadHeader
    # Withdrawals
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    # Deep history valid from Capella onwards
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
    # Sync history
    previous_best_sync_data: SyncData  # [New in Electra]
    current_best_sync_data: SyncData  # [New in Electra]
    parent_block_has_sync_committee_finality: bool  # [New in Electra]
```

## Beacon chain state transition function

### Epoch processing

#### Modified `process_sync_committee_updates`

```python
def process_sync_committee_updates(state: BeaconState) -> None:
    next_epoch = get_current_epoch(state) + Epoch(1)
    if next_epoch % EPOCHS_PER_SYNC_COMMITTEE_PERIOD == 0:
        state.current_sync_committee = state.next_sync_committee
        state.next_sync_committee = get_next_sync_committee(state)

        # [New in Electra]
        state.previous_best_sync_data = state.current_best_sync_data
        state.current_best_sync_data = SyncData()
        state.parent_block_has_sync_committee_finality = False
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_best_sync_data(state, block)  # [New in Electra]
    process_block_header(state, block)
    process_withdrawals(state, block.body.execution_payload)
    process_execution_payload(state, block.body, EXECUTION_ENGINE)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### New `process_best_sync_data`

```python
def process_best_sync_data(state: BeaconState, block: BeaconBlock) -> None:
    signature_period = compute_sync_committee_period_at_slot(block.slot)
    attested_period = compute_sync_committee_period_at_slot(state.latest_block_header.slot)

    # Track sync committee finality
    old_has_sync_committee_finality = state.parent_block_has_sync_committee_finality
    if state.parent_block_has_sync_committee_finality:
        new_has_sync_committee_finality = True
    elif state.finalized_checkpoint.epoch < ALTAIR_FORK_EPOCH:
        new_has_sync_committee_finality = False
    else:
        finalized_period = compute_sync_committee_period(state.finalized_checkpoint.epoch)
        new_has_sync_committee_finality = (finalized_period == attested_period)
    state.parent_block_has_sync_committee_finality = new_has_sync_committee_finality

    # Track best sync data
    if attested_period == signature_period:
        max_active_participants = len(block.body.sync_aggregate.sync_committee_bits)
        new_num_active_participants = sum(block.body.sync_aggregate.sync_committee_bits)
        old_num_active_participants = sum(state.current_best_sync_data.sync_aggregate.sync_committee_bits)
        new_has_supermajority = new_num_active_participants * 3 >= max_active_participants * 2
        old_has_supermajority = old_num_active_participants * 3 >= max_active_participants * 2
        if new_has_supermajority != old_has_supermajority:
            is_better_sync_data = new_has_supermajority
        elif not new_has_supermajority and new_num_active_participants != old_num_active_participants:
            is_better_sync_data = new_num_active_participants > old_num_active_participants
        elif new_has_sync_committee_finality != old_has_sync_committee_finality:
            is_better_sync_data = new_has_sync_committee_finality
        else:
            is_better_sync_data = new_num_active_participants > old_num_active_participants
        if is_better_sync_data:
            state.current_best_sync_data = SyncData(
                sync_aggregate=block.body.sync_aggregate,
                signature_slot=block.slot,
            )
```
