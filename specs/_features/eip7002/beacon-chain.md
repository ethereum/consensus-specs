# EIP-7002 -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Preset](#preset)
  - [Max operations per block](#max-operations-per-block)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`ExecutionLayerExit`](#executionlayerexit)
  - [Extended Containers](#extended-containers)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
    - [`BeaconState`](#beaconstate)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Modified `process_execution_payload`](#modified-process_execution_payload)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [New `process_execution_layer_exit`](#new-process_execution_layer_exit)
- [Testing](#testing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification of the execution layer triggerable exits feature.

This mechanism relies on the changes proposed by [EIP-7002](http://eips.ethereum.org/EIPS/eip-7002).

*Note:* This specification is built upon [Capella](../../capella/beacon-chain.md) and is under active development.

## Preset

### Max operations per block

| Name | Value |
| - | - |
| `MAX_EXECUTION_LAYER_EXITS` | `2**4` (= 16) |

## Containers

### New containers

#### `ExecutionLayerExit`

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
    exits: List[ExecutionLayerExit, MAX_EXECUTION_LAYER_EXITS]  # [New in EIP7002]
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
    exits_root: Root  # [New in EIP7002]
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
    latest_execution_payload_header: ExecutionPayloadHeader  # [Modified in EIP7002]
    # Withdrawals
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    # Deep history valid from Capella onwards
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
```

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
    # Verify the execution payload is valid
    assert execution_engine.verify_and_notify_new_payload(NewPayloadRequest(execution_payload=payload))
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
        exits_root=hash_tree_root(payload.exits),  # [New in EIP7002]
    )
```

#### Operations

##### Modified `process_operations`

*Note*: The function `process_operations` is modified to process `ExecutionLayerExit` operations included in the block.

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # Verify that outstanding deposits are processed up to the maximum number of deposits
    assert len(body.deposits) == min(MAX_DEPOSITS, state.eth1_data.deposit_count - state.eth1_deposit_index)

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.execution_payload.exits, process_execution_layer_exit)  # [New in EIP7002]
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
```

##### New `process_execution_layer_exit`

```python
def process_execution_layer_exit(state: BeaconState, execution_layer_exit: ExecutionLayerExit) -> None:
    validator_pubkeys = [v.pubkey for v in state.validators]
    validator_index = ValidatorIndex(validator_pubkeys.index(execution_layer_exit.validator_pubkey))
    validator = state.validators[validator_index]

    # Verify withdrawal credentials
    is_execution_address = validator.withdrawal_credentials[:1] == ETH1_ADDRESS_WITHDRAWAL_PREFIX
    is_correct_source_address = validator.withdrawal_credentials[12:] == execution_layer_exit.source_address
    if not (is_execution_address and is_correct_source_address):
        return
    # Verify the validator is active
    if not is_active_validator(validator, get_current_epoch(state)):
        return
    # Verify exit has not been initiated
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return
    # Verify the validator has been active long enough
    if get_current_epoch(state) < validator.activation_epoch + SHARD_COMMITTEE_PERIOD:
        return

    # Initiate exit
    initiate_validator_exit(state, validator_index)
```

## Testing

*Note*: The function `initialize_beacon_state_from_eth1` is modified for pure EIP-7002 testing only.
Modifications include:
1. Use `EIP7002_FORK_VERSION` as the previous and current fork version.
2. Utilize the EIP-7002 `BeaconBlockBody` when constructing the initial `latest_block_header`.

```python
def initialize_beacon_state_from_eth1(eth1_block_hash: Hash32,
                                      eth1_timestamp: uint64,
                                      deposits: Sequence[Deposit],
                                      execution_payload_header: ExecutionPayloadHeader=ExecutionPayloadHeader()
                                      ) -> BeaconState:
    fork = Fork(
        previous_version=EIP7002_FORK_VERSION,  # [Modified in EIP7002] for testing only
        current_version=EIP7002_FORK_VERSION,  # [Modified in EIP7002]
        epoch=GENESIS_EPOCH,
    )
    state = BeaconState(
        genesis_time=eth1_timestamp + GENESIS_DELAY,
        fork=fork,
        eth1_data=Eth1Data(block_hash=eth1_block_hash, deposit_count=uint64(len(deposits))),
        latest_block_header=BeaconBlockHeader(body_root=hash_tree_root(BeaconBlockBody())),
        randao_mixes=[eth1_block_hash] * EPOCHS_PER_HISTORICAL_VECTOR,  # Seed RANDAO with Eth1 entropy
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
