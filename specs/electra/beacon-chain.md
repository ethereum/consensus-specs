# Electra -- The Beacon Chain

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Misc](#misc)
- [Preset](#preset)
  - [Execution](#execution)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`DepositReceipt`](#depositreceipt)
    - [`ExecutionLayerExit`](#executionlayerexit)
  - [Extended Containers](#extended-containers)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
    - [`BeaconState`](#beaconstate)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Modified `process_operations`](#modified-process_operations)
    - [New `process_deposit_receipt`](#new-process_deposit_receipt)
    - [New `process_execution_layer_exit`](#new-process_execution_layer_exit)
    - [Modified `process_execution_payload`](#modified-process_execution_payload)
- [Testing](#testing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

Electra is a consensus-layer upgrade containing a number of features. Including:
* [EIP-6110](https://eips.ethereum.org/EIPS/eip-6110): Supply validator deposits on chain
* [EIP-7002](https://eips.ethereum.org/EIPS/eip-7002): Execution layer triggerable exits

## Constants

The following values are (non-configurable) constants used throughout the specification.

### Misc

| Name | Value | Description |
| - | - | - |
| `UNSET_DEPOSIT_RECEIPTS_START_INDEX` | `uint64(2**64 - 1)` | *[New in Electra:EIP6110]* |

## Preset

### Execution

| Name | Value | Description |
| - | - | - |
| `MAX_DEPOSIT_RECEIPTS_PER_PAYLOAD` | `uint64(2**13)` (= 8,192) | *[New in Electra:EIP6110]* Maximum number of deposit receipts allowed in each payload |
| `MAX_EXECUTION_LAYER_EXITS` | `2**4` (= 16) |  *[New in Electra:EIP7002]* |

## Containers

### New containers

#### `DepositReceipt`

*Note*: The container is new in EIP6110.

```python
class DepositReceipt(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
    amount: Gwei
    signature: BLSSignature
    index: uint64
```

#### `ExecutionLayerExit`

*Note*: The container is new in EIP7002.

```python
class ExecutionLayerExit(Container):
    source_address: ExecutionAddress
    validator_pubkey: BLSPubkey
```

### Extended Containers

#### `ExecutionPayload`

```python
class ExecutionPayload(Container):
    # Execution block header fields
    parent_hash: Hash32
    fee_recipient: ExecutionAddress
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    # Extra payload fields
    block_hash: Hash32
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
    blob_gas_used: uint64
    excess_blob_gas: uint64
    deposit_receipts: List[DepositReceipt, MAX_DEPOSIT_RECEIPTS_PER_PAYLOAD]  # [New in Electra:EIP6110]
    exits: List[ExecutionLayerExit, MAX_EXECUTION_LAYER_EXITS]  # [New in Electra:EIP7002]
```

#### `ExecutionPayloadHeader`

```python
class ExecutionPayloadHeader(Container):
    # Execution block header fields
    parent_hash: Hash32
    fee_recipient: ExecutionAddress
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    # Extra payload fields
    block_hash: Hash32
    transactions_root: Root
    withdrawals_root: Root
    blob_gas_used: uint64
    excess_blob_gas: uint64
    deposit_receipts_root: Root  # [New in Electra:EIP6110]
    exits_root: Root  # [New in Electra:EIP7002]
```

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
    latest_execution_payload_header: ExecutionPayloadHeader  # [Modified in Electra:EIP6110:EIP7002]
    # Withdrawals
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    # Deep history valid from Capella onwards
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
    # [New in Electra:EIP6110]
    deposit_receipts_start_index: uint64
```

## Beacon chain state transition function

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_withdrawals(state, block.body.execution_payload)
    process_execution_payload(state, block.body, EXECUTION_ENGINE)  # [Modified in Electra:EIP6110]
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)  # [Modified in Electra:EIP6110:EIP7002]
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### Modified `process_operations`

*Note*: The function `process_operations` is modified to process `DepositReceipt` and `ExecutionLayerExit` operations included in the payload.

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # [Modified in Electra:EIP6110]
    # Disable former deposit mechanism once all prior deposits are processed
    eth1_deposit_index_limit = min(state.eth1_data.deposit_count, state.deposit_receipts_start_index)
    if state.eth1_deposit_index < eth1_deposit_index_limit:
        assert len(body.deposits) == min(MAX_DEPOSITS, eth1_deposit_index_limit - state.eth1_deposit_index)
    else:
        assert len(body.deposits) == 0

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.execution_payload.exits, process_execution_layer_exit)  # [New in Electra:EIP7002]
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)

    # [New in EIP6110]
    for_ops(body.execution_payload.deposit_receipts, process_deposit_receipt)
```

#### New `process_deposit_receipt`

*Note*: This function is new in Electra:EIP6110.

```python
def process_deposit_receipt(state: BeaconState, deposit_receipt: DepositReceipt) -> None:
    # Set deposit receipt start index
    if state.deposit_receipts_start_index == UNSET_DEPOSIT_RECEIPTS_START_INDEX:
        state.deposit_receipts_start_index = deposit_receipt.index

    apply_deposit(
        state=state,
        pubkey=deposit_receipt.pubkey,
        withdrawal_credentials=deposit_receipt.withdrawal_credentials,
        amount=deposit_receipt.amount,
        signature=deposit_receipt.signature,
    )
```

#### New `process_execution_layer_exit`

*Note*: This function is new in Electra:EIP7002.

```python
def process_execution_layer_exit(state: BeaconState, execution_layer_exit: ExecutionLayerExit) -> None:
    validator_pubkeys = [v.pubkey for v in state.validators]
    # Verify pubkey exists
    pubkey_to_exit = execution_layer_exit.validator_pubkey
    assert pubkey_to_exit in validator_pubkeys
    validator_index = ValidatorIndex(validator_pubkeys.index(pubkey_to_exit))
    validator = state.validators[validator_index]
    # Verify withdrawal credentials
    is_execution_address = validator.withdrawal_credentials[:1] == ETH1_ADDRESS_WITHDRAWAL_PREFIX
    is_correct_source_address = validator.withdrawal_credentials[12:] == execution_layer_exit.source_address
    assert is_execution_address and is_correct_source_address
    # Verify the validator is active
    assert is_active_validator(validator, get_current_epoch(state))
    # Verify exit has not been initiated
    assert validator.exit_epoch == FAR_FUTURE_EPOCH
    # Verify the validator has been active long enough
    assert get_current_epoch(state) >= validator.activation_epoch + SHARD_COMMITTEE_PERIOD
    # Initiate exit
    initiate_validator_exit(state, validator_index)
```

#### Modified `process_execution_payload`

*Note*: The function `process_execution_payload` is modified to use the new `ExecutionPayloadHeader` type.

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
    assert len(body.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK
    # Verify the execution payload is valid
    versioned_hashes = [kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments]
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
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
        deposit_receipts_root=hash_tree_root(payload.deposit_receipts),  # [New in Electra:EIP6110]
        exits_root=hash_tree_root(payload.exits),  # [New in Electra:EIP7002]
    )
```

## Testing

*Note*: The function `initialize_beacon_state_from_eth1` is modified for pure Electra testing only.
Modifications include:
1. Use `ELECTRA_FORK_VERSION` as the previous and current fork version.
2. Utilize the Electra `BeaconBlockBody` when constructing the initial `latest_block_header`.
3. *[New in Electra:EIP6110]* Add `deposit_receipts_start_index` variable to the genesis state initialization.

```python
def initialize_beacon_state_from_eth1(eth1_block_hash: Hash32,
                                      eth1_timestamp: uint64,
                                      deposits: Sequence[Deposit],
                                      execution_payload_header: ExecutionPayloadHeader=ExecutionPayloadHeader()
                                      ) -> BeaconState:
    fork = Fork(
        previous_version=ELECTRA_FORK_VERSION,  # [Modified in Electra:EIP6110] for testing only
        current_version=ELECTRA_FORK_VERSION,  # [Modified in Electra:EIP6110]
        epoch=GENESIS_EPOCH,
    )
    state = BeaconState(
        genesis_time=eth1_timestamp + GENESIS_DELAY,
        fork=fork,
        eth1_data=Eth1Data(block_hash=eth1_block_hash, deposit_count=uint64(len(deposits))),
        latest_block_header=BeaconBlockHeader(body_root=hash_tree_root(BeaconBlockBody())),
        randao_mixes=[eth1_block_hash] * EPOCHS_PER_HISTORICAL_VECTOR,  # Seed RANDAO with Eth1 entropy
        deposit_receipts_start_index=UNSET_DEPOSIT_RECEIPTS_START_INDEX,  # [New in Electra:EIP6110]
    )

    # Process deposits
    leaves = list(map(lambda deposit: deposit.data, deposits))
    for index, deposit in enumerate(deposits):
        deposit_data_list = List[DepositData, 2**DEPOSIT_CONTRACT_TREE_DEPTH](*leaves[:index + 1])
        state.eth1_data.deposit_root = hash_tree_root(deposit_data_list)
        process_deposit(state, deposit)

    # Process activations
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        validator.effective_balance = min(balance - balance % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE)
        if validator.effective_balance == MAX_EFFECTIVE_BALANCE:
            validator.activation_eligibility_epoch = GENESIS_EPOCH
            validator.activation_epoch = GENESIS_EPOCH

    # Set genesis validators root for domain separation and chain versioning
    state.genesis_validators_root = hash_tree_root(state.validators)

    # Fill in sync committees
    # Note: A duplicate committee is assigned for the current and next committee at genesis
    state.current_sync_committee = get_next_sync_committee(state)
    state.next_sync_committee = get_next_sync_committee(state)

    # Initialize the execution payload header
    state.latest_execution_payload_header = execution_payload_header

    return state
```
