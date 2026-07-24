# Fulu -- The Beacon Chain

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `ProposerIndices`](#new-proposerindices)
  - [New `ProposerLookahead`](#new-proposerlookahead)
- [Configuration](#configuration)
  - [Blob schedule](#blob-schedule)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Modified `process_execution_payload`](#modified-process_execution_payload)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [Deposit requests](#deposit-requests)
        - [Modified `process_deposit_request`](#modified-process_deposit_request)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`BeaconState`](#beaconstate)
- [Helpers](#helpers)
  - [Misc](#misc)
    - [New `BlobParameters`](#new-blobparameters)
    - [New `get_blob_parameters`](#new-get_blob_parameters)
    - [Modified `compute_fork_digest`](#modified-compute_fork_digest)
    - [New `compute_proposer_indices`](#new-compute_proposer_indices)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Modified `get_beacon_proposer_index`](#modified-get_beacon_proposer_index)
    - [New `get_beacon_proposer_indices`](#new-get_beacon_proposer_indices)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [Modified `process_pending_deposits`](#modified-process_pending_deposits)
    - [New `process_proposer_lookahead`](#new-process_proposer_lookahead)

<!-- mdformat-toc end -->

## Introduction

Fulu is a consensus-layer upgrade containing a number of features. Including:

- [EIP-7594](https://eips.ethereum.org/EIPS/eip-7594): PeerDAS - Peer Data
  Availability Sampling
- [EIP-7917](https://eips.ethereum.org/EIPS/eip-7917): Deterministic proposer
  lookahead
- [EIP-7892](https://eips.ethereum.org/EIPS/eip-7892): Blob Parameter Only
  Hardforks

## Types

### New `ProposerIndices`

```python
class ProposerIndices(Vector[ValidatorIndex, SLOTS_PER_EPOCH]):
    pass
```

### New `ProposerLookahead`

```python
class ProposerLookahead(Vector[ValidatorIndex, (MIN_SEED_LOOKAHEAD + 1) * SLOTS_PER_EPOCH]):
    pass
```

## Configuration

### Blob schedule

*[New in Fulu:EIP7892]* This schedule defines the maximum blobs per block limit
for a given epoch.

There MUST NOT exist multiple blob schedule entries with the same epoch value.
The epoch value in each entry MUST be greater than or equal to
`FULU_FORK_EPOCH`. The maximum blobs per block limit in each entry MUST be less
than or equal to `MAX_BLOB_COMMITMENTS_PER_BLOCK`. The blob schedule entries
SHOULD be sorted by epoch in ascending order. The blob schedule MAY be empty.

<!-- list-of-records:blob_schedule -->

|  Epoch | Max Blobs Per Block |                             Date |
| -----: | ------------------: | -------------------------------: |
| 412672 |                  15 | December 9, 2025, 02:21:11pm UTC |
| 419072 |                  21 |  January 7, 2026, 01:01:11am UTC |

## Beacon chain state transition function

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_withdrawals(state, block.body.execution_payload)
    process_execution_payload(state, block.body, EXECUTION_ENGINE)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    # [Modified in Fulu]
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### Execution payload

##### Modified `process_execution_payload`

```python
def process_execution_payload(
    state: BeaconState, body: BeaconBlockBody, execution_engine: ExecutionEngine
) -> None:
    payload = body.execution_payload

    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_time_at_slot(state, state.slot)
    # [Modified in Fulu:EIP7892]
    # Verify commitments are under limit
    assert (
        len(body.blob_kzg_commitments)
        <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
    )

    # Compute list of versioned hashes
    versioned_hashes = [
        kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments
    ]

    # Verify the execution payload is valid
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

#### Operations

##### Modified `process_operations`

*Note*: The function `process_operations` is modified to remove support for the
former deposit mechanism.

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # [Modified in Fulu]
    assert len(body.deposits) == 0

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    for_ops(body.attestations, process_attestation)
    # [Modified in Fulu]
    # Removed `process_deposit`
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    for_ops(body.execution_requests.deposits, process_deposit_request)
    for_ops(body.execution_requests.withdrawals, process_withdrawal_request)
    for_ops(body.execution_requests.consolidations, process_consolidation_request)
```

##### Deposit requests

###### Modified `process_deposit_request`

*Note*: The function `process_deposit_request` is modified to remove support for
the former deposit mechanism.

```python
def process_deposit_request(state: BeaconState, deposit_request: DepositRequest) -> None:
    state.pending_deposits.append(
        PendingDeposit(
            pubkey=deposit_request.pubkey,
            withdrawal_credentials=deposit_request.withdrawal_credentials,
            amount=deposit_request.amount,
            signature=deposit_request.signature,
            slot=state.slot,
        )
    )
```

## Containers

### Modified containers

#### `BeaconState`

*Note*: The `BeaconState` container is extended with the `proposer_lookahead`
field, which is a list of validator indices covering the full lookahead period,
starting from the beginning of the current epoch. For example,
`proposer_lookahead[0]` is the validator index for the first proposer in the
current epoch, `proposer_lookahead[1]` is the validator index for the next
proposer in the current epoch, and so forth. The length of the
`proposer_lookahead` list is `(MIN_SEED_LOOKAHEAD + 1) * SLOTS_PER_EPOCH`,
reflecting how far ahead proposer indices are computed based on the
`MIN_SEED_LOOKAHEAD` parameter.

```python
class BeaconState(Container):
    genesis_time: Uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    latest_block_header: BeaconBlockHeader
    block_roots: BlockRoots
    state_roots: StateRoots
    historical_roots: HistoricalRoots
    eth1_data: Eth1Data
    eth1_data_votes: Eth1DataVotes
    eth1_deposit_index: Uint64
    validators: Validators
    balances: Balances
    randao_mixes: RandaoMixes
    slashings: Slashings
    previous_epoch_participation: EpochParticipation
    current_epoch_participation: EpochParticipation
    justification_bits: JustificationBits
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    inactivity_scores: InactivityScores
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    latest_execution_payload_header: ExecutionPayloadHeader
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    historical_summaries: HistoricalSummaries
    deposit_requests_start_index: Uint64
    deposit_balance_to_consume: Gwei
    exit_balance_to_consume: Gwei
    earliest_exit_epoch: Epoch
    consolidation_balance_to_consume: Gwei
    earliest_consolidation_epoch: Epoch
    pending_deposits: PendingDeposits
    pending_partial_withdrawals: PendingPartialWithdrawals
    pending_consolidations: PendingConsolidations
    # [New in Fulu:EIP7917]
    proposer_lookahead: ProposerLookahead
```

## Helpers

### Misc

#### New `BlobParameters`

```python
@dataclass
class BlobParameters:
    epoch: Epoch
    max_blobs_per_block: Uint64
```

#### New `get_blob_parameters`

```python
def get_blob_parameters(epoch: Epoch) -> BlobParameters:
    """
    Return the blob parameters at a given epoch.
    """
    for entry in sorted(BLOB_SCHEDULE, key=lambda e: e["EPOCH"], reverse=True):
        if epoch >= entry["EPOCH"]:
            return BlobParameters(entry["EPOCH"], entry["MAX_BLOBS_PER_BLOCK"])
    return BlobParameters(ELECTRA_FORK_EPOCH, MAX_BLOBS_PER_BLOCK_ELECTRA)
```

#### Modified `compute_fork_digest`

*Note*: The `compute_fork_digest` helper is updated to account for
Blob-Parameters-Only forks.

```python
def compute_fork_digest(
    genesis_validators_root: Root,
    epoch: Epoch,
) -> ForkDigest:
    """
    Return the 4-byte fork digest for the ``genesis_validators_root`` at a given ``epoch``.

    This is a digest primarily used for domain separation on the p2p layer.
    4-bytes suffices for practical separation of forks/chains.
    """
    fork_version = compute_fork_version(epoch)
    base_digest = compute_fork_data_root(fork_version, genesis_validators_root)

    # [New in Fulu:EIP7892]
    if epoch < FULU_FORK_EPOCH:
        return ForkDigest(base_digest[:4])

    # [Modified in Fulu:EIP7892]
    # Bitmask digest with hash of blob parameters
    blob_parameters = get_blob_parameters(epoch)
    return ForkDigest(
        bytes(
            xor(
                base_digest,
                hash(
                    uint_to_bytes(Uint64(blob_parameters.epoch))
                    + uint_to_bytes(Uint64(blob_parameters.max_blobs_per_block))
                ),
            )
        )[:4]
    )
```

#### New `compute_proposer_indices`

```python
def compute_proposer_indices(
    state: BeaconState, epoch: Epoch, seed: Bytes32, indices: Sequence[ValidatorIndex]
) -> ProposerIndices:
    """
    Return the proposer indices for the given ``epoch``.
    """
    start_slot = compute_start_slot_at_epoch(epoch)
    seeds = [hash(seed + uint_to_bytes(Slot(start_slot + i))) for i in range(SLOTS_PER_EPOCH)]
    return ProposerIndices(compute_proposer_index(state, indices, seed) for seed in seeds)
```

### Beacon state accessors

#### Modified `get_beacon_proposer_index`

*Note*: The function `get_beacon_proposer_index` is modified to use the
pre-calculated `proposer_lookahead` instead of calculating it on-demand.

```python
def get_beacon_proposer_index(state: BeaconState) -> ValidatorIndex:
    """
    Return the beacon proposer index at the current slot.
    """
    return state.proposer_lookahead[state.slot % SLOTS_PER_EPOCH]
```

#### New `get_beacon_proposer_indices`

```python
def get_beacon_proposer_indices(state: BeaconState, epoch: Epoch) -> ProposerIndices:
    """
    Return the proposer indices for the given ``epoch``.
    """
    indices = get_active_validator_indices(state, epoch)
    seed = get_seed(state, epoch, DOMAIN_BEACON_PROPOSER)
    return compute_proposer_indices(state, epoch, seed, indices)
```

### Epoch processing

#### Modified `process_epoch`

*Note*: The function `process_epoch` is modified in Fulu to call
`process_proposer_lookahead` to update the `proposer_lookahead` in the beacon
state.

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
    # [New in Fulu:EIP7917]
    process_proposer_lookahead(state)
```

#### Modified `process_pending_deposits`

*Note*: The function `process_pending_deposits` is modified to remove support
for the former deposit mechanism.

```python
def process_pending_deposits(state: BeaconState) -> None:
    next_epoch = Epoch(get_current_epoch(state) + 1)
    available_for_processing = state.deposit_balance_to_consume + get_activation_exit_churn_limit(
        state
    )
    processed_amount = 0
    next_deposit_index = 0
    deposits_to_postpone = []
    is_churn_limit_reached = False
    finalized_slot = compute_start_slot_at_epoch(state.finalized_checkpoint.epoch)

    for deposit in state.pending_deposits:
        # Check if deposit has been finalized, otherwise, stop processing.
        if deposit.slot > finalized_slot:
            break

        # Check if number of processed deposits has not reached the limit, otherwise, stop processing.
        if next_deposit_index >= MAX_PENDING_DEPOSITS_PER_EPOCH:
            break

        # Read validator state
        is_validator_exited = False
        is_validator_withdrawn = False
        validator_pubkeys = [v.pubkey for v in state.validators]
        if deposit.pubkey in validator_pubkeys:
            validator = state.validators[ValidatorIndex(validator_pubkeys.index(deposit.pubkey))]
            is_validator_exited = validator.exit_epoch < FAR_FUTURE_EPOCH
            is_validator_withdrawn = validator.withdrawable_epoch < next_epoch

        if is_validator_withdrawn:
            # Deposited balance will never become active. Increase balance but do not consume churn
            apply_pending_deposit(state, deposit)
        elif is_validator_exited:
            # Validator is exiting, postpone the deposit until after withdrawable epoch
            deposits_to_postpone.append(deposit)
        else:
            # Check if deposit fits in the churn, otherwise, do no more deposit processing in this epoch.
            is_churn_limit_reached = processed_amount + deposit.amount > available_for_processing
            if is_churn_limit_reached:
                break

            # Consume churn and apply deposit.
            processed_amount += deposit.amount
            apply_pending_deposit(state, deposit)

        # Regardless of how the deposit was handled, we move on in the queue.
        next_deposit_index += 1

    state.pending_deposits = state.pending_deposits[next_deposit_index:] + deposits_to_postpone

    # Accumulate churn only if the churn limit has been hit.
    if is_churn_limit_reached:
        state.deposit_balance_to_consume = available_for_processing - processed_amount
    else:
        state.deposit_balance_to_consume = Gwei(0)
```

#### New `process_proposer_lookahead`

*Note*: This function updates the `proposer_lookahead` field in the beacon state
by shifting out proposer indices from the earliest epoch and appending new
proposer indices for the latest epoch. With `MIN_SEED_LOOKAHEAD` set to `1`,
this means that at the start of epoch `N`, the proposer lookahead for epoch
`N+1` will be computed and included in the beacon state's lookahead.

```python
def process_proposer_lookahead(state: BeaconState) -> None:
    last_epoch_start = len(state.proposer_lookahead) - SLOTS_PER_EPOCH
    # Shift out proposers in the first epoch
    state.proposer_lookahead[:last_epoch_start] = state.proposer_lookahead[SLOTS_PER_EPOCH:]
    # Fill in the last epoch with new proposer indices
    last_epoch_proposers = get_beacon_proposer_indices(
        state, Epoch(get_current_epoch(state) + MIN_SEED_LOOKAHEAD + 1)
    )
    state.proposer_lookahead[last_epoch_start:] = last_epoch_proposers
```
