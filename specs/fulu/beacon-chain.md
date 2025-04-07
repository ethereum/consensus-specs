# Fulu -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Execution](#execution)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Modified `process_execution_payload`](#modified-process_execution_payload)
- [Containers](#containers)
  - [Extended Containers](#extended-containers)
    - [`BeaconState`](#beaconstate)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [New `compute_proposer_indices`](#new-compute_proposer_indices)
    - [New `initialize_proposer_lookahead`](#new-initialize_proposer_lookahead)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Modified `get_beacon_proposer_index`](#modified-get_beacon_proposer_index)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [New `process_proposer_lookahead`](#new-process_proposer_lookahead)

<!-- mdformat-toc end -->

## Introduction

*Note*: This specification is built upon [Electra](../electra/beacon-chain.md) and is under active development.

## Configuration

### Execution

| Name                       | Value        | Description                                                                                                   |
| -------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------- |
| `MAX_BLOBS_PER_BLOCK_FULU` | `uint64(12)` | *[New in Fulu:EIP7594]* Maximum number of blobs in a single block limited by `MAX_BLOB_COMMITMENTS_PER_BLOCK` |

## Beacon chain state transition function

### Block processing

#### Execution payload

##### Modified `process_execution_payload`

```python
def process_execution_payload(state: BeaconState, body: BeaconBlockBody, execution_engine: ExecutionEngine) -> None:
    payload = body.execution_payload

    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)
    # Verify commitments are under limit
    assert len(body.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK_FULU  # [Modified in Fulu:EIP7594]
    # Verify the execution payload is valid
    versioned_hashes = [kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments]
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
            execution_requests=body.execution_requests,
        )
    )
    # Cache execution payload header
    state.latest_execution_payload_header = ExecutionPayloadHeader(
        parent_hash=payload.parent_hash,
        fee_recipient=payload.fee_recipient,
        state_root=payload.state_root,
        receipts_root=payload.receipts_root,
        logs_bloom=payload.logs_bloom,
        prev_randao=payload.prev_randao,
        block_number=payload.block_number,
        gas_limit=payload.gas_limit,
        gas_used=payload.gas_used,
        timestamp=payload.timestamp,
        extra_data=payload.extra_data,
        base_fee_per_gas=payload.base_fee_per_gas,
        block_hash=payload.block_hash,
        transactions_root=hash_tree_root(payload.transactions),
        withdrawals_root=hash_tree_root(payload.withdrawals),
        blob_gas_used=payload.blob_gas_used,
        excess_blob_gas=payload.excess_blob_gas,
    )
```

## Containers

### Extended Containers

#### `BeaconState`

*Note*: The `BeaconState` container is extended with the `proposer_lookahead` field, which is a list of validator indices covering the full lookahead period, starting from the beginning of the current epoch. For example, `proposer_lookahead[0]` is the validator index for the first proposer in the current epoch, `proposer_lookahead[1]` is the validator index for the next proposer in the current epoch, and so forth. The length of the `proposer_lookahead` list is `(MIN_SEED_LOOKAHEAD + 1) * SLOTS_PER_EPOCH`, reflecting how far ahead proposer indices are computed based on the `MIN_SEED_LOOKAHEAD` parameter.

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
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]
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
    deposit_requests_start_index: uint64
    deposit_balance_to_consume: Gwei
    exit_balance_to_consume: Gwei
    earliest_exit_epoch: Epoch
    consolidation_balance_to_consume: Gwei
    earliest_consolidation_epoch: Epoch
    pending_deposits: List[PendingDeposit, PENDING_DEPOSITS_LIMIT]
    pending_partial_withdrawals: List[PendingPartialWithdrawal, PENDING_PARTIAL_WITHDRAWALS_LIMIT]
    pending_consolidations: List[PendingConsolidation, PENDING_CONSOLIDATIONS_LIMIT]
    proposer_lookahead: List[ValidatorIndex, (MIN_SEED_LOOKAHEAD + 1) * SLOTS_PER_EPOCH]  # [New in Fulu:EIP7917]
```

## Helper functions

### Misc

#### New `compute_proposer_indices`

```python
def compute_proposer_indices(state: BeaconState, epoch: Epoch) -> List[ValidatorIndex, SLOTS_PER_EPOCH]:
    """
    Return the proposer indices for the given `epoch`.
    """
    epoch_seed = get_seed(state, epoch, DOMAIN_BEACON_PROPOSER)
    start_slot = compute_start_slot_at_epoch(epoch)
    seeds = [hash(epoch_seed + uint_to_bytes(Slot(start_slot + i))) for i in range(SLOTS_PER_EPOCH)]
    indices = get_active_validator_indices(state, epoch)
    return [compute_proposer_index(state, indices, seed) for seed in seeds]
```

#### New `initialize_proposer_lookahead`

```python
def initialize_proposer_lookahead(
    state: BeaconState
) -> List[ValidatorIndex, (MIN_SEED_LOOKAHEAD + 1) * SLOTS_PER_EPOCH]:
    """
    Return the proposer indices for the full available lookahead starting from current epoch.
    Used to initialize the `proposer_lookahead` field in the beacon state at genesis and after forks.
    """
    current_epoch = get_current_epoch(state)
    lookahead = []
    for i in range(MIN_SEED_LOOKAHEAD + 1):
        lookahead.extend(compute_proposer_indices(state, Epoch(current_epoch + i)))
    return lookahead
```

### Beacon state accessors

#### Modified `get_beacon_proposer_index`

*Note*: The function `get_beacon_proposer_index` is modified to use the pre-calculated `current_proposer_lookahead` instead of calculating it on-demand.

```python
def get_beacon_proposer_index(state: BeaconState) -> ValidatorIndex:
    """
    Return the beacon proposer index at the current slot.
    """
    return state.proposer_lookahead[state.slot % SLOTS_PER_EPOCH]
```

### Epoch processing

#### Modified `process_epoch`

*Note*: The function `process_epoch` is modified in Fulu to call `process_proposer_lookahead` to update the `proposer_lookahead` in the beacon state.

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_pending_deposits(state)
    process_pending_consolidations(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
    process_proposer_lookahead(state)  # [New in Fulu:EIP7917]
```

#### New `process_proposer_lookahead`

*Note*: This function updates the `proposer_lookahead` field in the beacon state by shifting out proposer indices from the earliest epoch and appending new proposer indices for the latest epoch. With `MIN_SEED_LOOKAHEAD` set to `1`, this means that at the start of epoch `N`, the proposer lookahead for epoch `N+1` will be computed and included in the beacon state's lookahead.

```python
def process_proposer_lookahead(state: BeaconState) -> None:
    last_epoch_start = len(state.proposer_lookahead) - SLOTS_PER_EPOCH
    # Shift out proposers in the first epoch
    state.proposer_lookahead[:last_epoch_start] = state.proposer_lookahead[SLOTS_PER_EPOCH:]
    # Fill in the last epoch with new proposer indices
    last_epoch_proposers = compute_proposer_indices(state, Epoch(get_current_epoch(state) + MIN_SEED_LOOKAHEAD + 1))
    state.proposer_lookahead[last_epoch_start:] = last_epoch_proposers
```