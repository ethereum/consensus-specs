# Capella -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
  - [Domain types](#domain-types)
- [Preset](#preset)
  - [Misc](#misc)
  - [State list lengths](#state-list-lengths)
  - [Max operations per block](#max-operations-per-block)
  - [Execution](#execution)
- [Configuration](#configuration)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`Withdrawal`](#withdrawal)
    - [`BLSToExecutionChange`](#blstoexecutionchange)
    - [`SignedBLSToExecutionChange`](#signedblstoexecutionchange)
  - [Extended Containers](#extended-containers)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
    - [`Validator`](#validator)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
- [Helpers](#helpers)
  - [Beacon state mutators](#beacon-state-mutators)
    - [`withdraw`](#withdraw)
  - [Predicates](#predicates)
    - [`has_eth1_withdrawal_credential`](#has_eth1_withdrawal_credential)
    - [`is_fully_withdrawable_validator`](#is_fully_withdrawable_validator)
    - [`is_partially_withdrawable_validator`](#is_partially_withdrawable_validator)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Full withdrawals](#full-withdrawals)
    - [Partial withdrawals](#partial-withdrawals)
  - [Block processing](#block-processing)
    - [New `process_withdrawals`](#new-process_withdrawals)
    - [Modified `process_execution_payload`](#modified-process_execution_payload)
    - [Modified `process_operations`](#modified-process_operations)
    - [New `process_bls_to_execution_change`](#new-process_bls_to_execution_change)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

Capella is a consensus-layer upgrade containing a number of features related
to validator withdrawals. Including:
* Automatic withdrawals of `withdrawable` validators
* Partial withdrawals sweep for validators with 0x01 withdrawal
  credentials and balances in exceess of `MAX_EFFECTIVE_BALANCE`
* Operation to change from `BLS_WITHDRAWAL_PREFIX` to
  `ETH1_ADDRESS_WITHDRAWAL_PREFIX` versioned withdrawal credentials to enable withdrawals for a validator

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `WithdrawalIndex` | `uint64` | an index of a `Withdrawal`|

## Constants

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_BLS_TO_EXECUTION_CHANGE` | `DomainType('0x0A000000')` |

## Preset

### Misc

| Name | Value |
| - | - |
| `MAX_PARTIAL_WITHDRAWALS_PER_EPOCH` | `uint64(2**8)` (= 256) |

### State list lengths

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `WITHDRAWAL_QUEUE_LIMIT` | `uint64(2**40)` (= 1,099,511,627,776) | withdrawals enqueued in state|

### Max operations per block

| Name | Value |
| - | - |
| `MAX_BLS_TO_EXECUTION_CHANGES` | `2**4` (= 16) |

### Execution

| Name | Value | Description |
| - | - | - |
| `MAX_WITHDRAWALS_PER_PAYLOAD` | `uint64(2**4)` (= 16) | Maximum amount of withdrawals allowed in each payload |

## Configuration

## Containers

### New containers

#### `Withdrawal`

```python
class Withdrawal(Container):
    index: WithdrawalIndex
    address: ExecutionAddress
    amount: Gwei
```

#### `BLSToExecutionChange`

```python
class BLSToExecutionChange(Container):
    validator_index: ValidatorIndex
    from_bls_pubkey: BLSPubkey
    to_execution_address: ExecutionAddress
```

#### `SignedBLSToExecutionChange`

```python
class SignedBLSToExecutionChange(Container):
    message: BLSToExecutionChange
    signature: BLSSignature
```

### Extended Containers

#### `ExecutionPayload`

```python
class ExecutionPayload(Container):
    # Execution block header fields
    parent_hash: Hash32
    fee_recipient: ExecutionAddress  # 'beneficiary' in the yellow paper
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32  # 'difficulty' in the yellow paper
    block_number: uint64  # 'number' in the yellow paper
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    # Extra payload fields
    block_hash: Hash32  # Hash of execution block
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]  # [New in Capella]
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
    block_hash: Hash32  # Hash of execution block
    transactions_root: Root
    withdrawals_root: Root  # [New in Capella]
```

#### `Validator`

```python
class Validator(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32  # Commitment to pubkey for withdrawals
    effective_balance: Gwei  # Balance at stake
    slashed: boolean
    # Status epochs
    activation_eligibility_epoch: Epoch  # When criteria for activation were met
    activation_epoch: Epoch
    exit_epoch: Epoch
    withdrawable_epoch: Epoch  # When validator can withdraw funds
    fully_withdrawn_epoch: Epoch  # [New in Capella]
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data  # Eth1 data vote
    graffiti: Bytes32  # Arbitrary data
    # Operations
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    # Execution
    execution_payload: ExecutionPayload
    # Capella operations
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]  # [New in Capella]
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
    latest_execution_payload_header: ExecutionPayloadHeader
    # Withdrawals
    withdrawal_queue: List[Withdrawal, WITHDRAWAL_QUEUE_LIMIT]  # [New in Capella]
    next_withdrawal_index: WithdrawalIndex  # [New in Capella]
    next_partial_withdrawal_validator_index: ValidatorIndex  # [New in Capella]
```

## Helpers

### Beacon state mutators

#### `withdraw`

```python
def withdraw_balance(state: BeaconState, index: ValidatorIndex, amount: Gwei) -> None:
    # Decrease the validator's balance
    decrease_balance(state, index, amount)
    # Create a corresponding withdrawal receipt
    withdrawal = Withdrawal(
        index=state.next_withdrawal_index,
        address=ExecutionAddress(state.validators[index].withdrawal_credentials[12:]),
        amount=amount,
    )
    state.next_withdrawal_index = WithdrawalIndex(state.next_withdrawal_index + 1)
    state.withdrawal_queue.append(withdrawal)
```

### Predicates

#### `has_eth1_withdrawal_credential`

```python
def has_eth1_withdrawal_credential(validator: Validator) -> bool:
    """
    Check if ``validator`` has an 0x01 prefixed "eth1" withdrawal credential
    """
    return validator.withdrawal_credentials[:1] == ETH1_ADDRESS_WITHDRAWAL_PREFIX
```

#### `is_fully_withdrawable_validator`

```python
def is_fully_withdrawable_validator(validator: Validator, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is fully withdrawable.
    """
    return (
        has_eth1_withdrawal_credential(validator)
        and validator.withdrawable_epoch <= epoch < validator.fully_withdrawn_epoch
    )
```

#### `is_partially_withdrawable_validator`

```python
def is_partially_withdrawable_validator(validator: Validator, balance: Gwei) -> bool:
    """
    Check if ``validator`` is partially withdrawable.
    """
    has_max_effective_balance = validator.effective_balance == MAX_EFFECTIVE_BALANCE
    has_excess_balance = balance > MAX_EFFECTIVE_BALANCE
    return has_eth1_withdrawal_credential(validator) and has_max_effective_balance and has_excess_balance
```

## Beacon chain state transition function

### Epoch processing

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_roots_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
    process_full_withdrawals(state)  # [New in Capella]
    process_partial_withdrawals(state)  # [New in Capella]

```

#### Full withdrawals

*Note*: The function `process_full_withdrawals` is new.

```python
def process_full_withdrawals(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    for index, validator in enumerate(state.validators):
        if is_fully_withdrawable_validator(validator, current_epoch):
            # TODO, consider the zero-balance case
            withdraw_balance(state, ValidatorIndex(index), state.balances[index])
            validator.fully_withdrawn_epoch = current_epoch
```

#### Partial withdrawals

*Note*: The function `process_partial_withdrawals` is new.

```python
def process_partial_withdrawals(state: BeaconState) -> None:
    partial_withdrawals_count = 0
    # Begin where we left off last time
    validator_index = state.next_partial_withdrawal_validator_index
    for _ in range(len(state.validators)):
        balance = state.balances[validator_index]
        validator = state.validators[validator_index]
        if is_partially_withdrawable_validator(validator, balance):
            withdraw_balance(state, validator_index, balance - MAX_EFFECTIVE_BALANCE)
            partial_withdrawals_count += 1

        # Iterate to next validator to check for partial withdrawal
        validator_index = ValidatorIndex((validator_index + 1) % len(state.validators))
        # Exit if performed maximum allowable withdrawals
        if partial_withdrawals_count == MAX_PARTIAL_WITHDRAWALS_PER_EPOCH:
            break

    state.next_partial_withdrawal_validator_index = validator_index
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    if is_execution_enabled(state, block.body):
        process_withdrawals(state, block.body.execution_payload)  # [New in Capella]
        process_execution_payload(state, block.body.execution_payload, EXECUTION_ENGINE)  # [Modified in Capella]
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### New `process_withdrawals`

```python
def process_withdrawals(state: BeaconState, payload: ExecutionPayload) -> None:
    num_withdrawals = min(MAX_WITHDRAWALS_PER_PAYLOAD, len(state.withdrawal_queue))
    dequeued_withdrawals = state.withdrawal_queue[:num_withdrawals]

    assert len(dequeued_withdrawals) == len(payload.withdrawals)
    for dequeued_withdrawal, withdrawal in zip(dequeued_withdrawals, payload.withdrawals):
        assert dequeued_withdrawal == withdrawal

    # Remove dequeued withdrawals from state
    state.withdrawal_queue = state.withdrawal_queue[num_withdrawals:]
```

#### Modified `process_execution_payload`

*Note*: The function `process_execution_payload` is modified to use the new `ExecutionPayloadHeader` type.

```python
def process_execution_payload(state: BeaconState, payload: ExecutionPayload, execution_engine: ExecutionEngine) -> None:
    # Verify consistency of the parent hash with respect to the previous execution payload header
    if is_merge_transition_complete(state):
        assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)
    # Verify the execution payload is valid
    assert execution_engine.notify_new_payload(payload)
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
        withdrawals_root=hash_tree_root(payload.withdrawals),  # [New in Capella]
    )
```

#### Modified `process_operations`

*Note*: The function `process_operations` is modified to process `BLSToExecutionChange` operations included in the block.

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
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)  # [New in Capella]
```

#### New `process_bls_to_execution_change`

```python
def process_bls_to_execution_change(state: BeaconState,
                                    signed_address_change: SignedBLSToExecutionChange) -> None:
    address_change = signed_address_change.message

    assert address_change.validator_index < len(state.validators)

    validator = state.validators[address_change.validator_index]

    assert validator.withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX
    assert validator.withdrawal_credentials[1:] == hash(address_change.from_bls_pubkey)[1:]

    domain = get_domain(state, DOMAIN_BLS_TO_EXECUTION_CHANGE)
    signing_root = compute_signing_root(address_change, domain)
    assert bls.Verify(address_change.from_bls_pubkey, signing_root, signed_address_change.signature)

    validator.withdrawal_credentials = (
        ETH1_ADDRESS_WITHDRAWAL_PREFIX
        + b'\x00' * 11
        + address_change.to_execution_address
    )
```
