# DepositEIP -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Preset](#preset)
  - [State list lengths](#state-list-lengths)
  - [Execution](#execution)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`DepositReceipt`](#depositreceipt)
    - [`IndexedDepositData`](#indexeddepositdata)
  - [Extended Containers](#extended-containers)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
    - [`BeaconState`](#beaconstate)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Helper functions](#helper-functions)
      - [New `get_validator_from_indexed_deposit_data`](#new-get_validator_from_indexed_deposit_data)
      - [New `apply_pending_deposit`](#new-apply_pending_deposit)
    - [New `process_pending_deposits`](#new-process_pending_deposits)
  - [Block processing](#block-processing)
    - [New `process_deposit_receipts`](#new-process_deposit_receipts)
    - [Modified `process_execution_payload`](#modified-process_execution_payload)
    - [Modified `process_operations`](#modified-process_operations)
- [Testing](#testing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification of in-protocol deposits processing mechanism.
This mechanism relies on the changes proposed by the corresponding EIP.

*Note:* This specification is under development and should be used with care.

## Preset

### State list lengths

| Name | Value |
| - | - |
| `PENDING_DEPOSITS_LIMIT` | `2**32` (= 4,294,967,296) |

### Execution

| Name | Value | Description |
| - | - | - |
| `MAX_DEPOSIT_RECEIPTS_PER_PAYLOAD` | `uint64(2**10)` (= 1,024) | Maximum number of deposit receipts allowed in each payload |

## Containers

### New containers

#### `DepositReceipt`

```python
class DepositReceipt(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
    amount: Gwei
    signature: BLSSignature
    index: uint64
```

#### `IndexedDepositData`

```python
class IndexedDepositData(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
    amount: Gwei
    index: uint64
    epoch: Epoch
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
    deposit_receipts: List[DepositReceipt, MAX_DEPOSIT_RECEIPTS_PER_PAYLOAD]  # [New in DepositEIP]
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
    deposit_receipts_root: Root  # [New in DepositEIP]
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
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    # DepositsEIP
    pending_deposits: List[IndexedDepositData, PENDING_DEPOSITS_LIMIT]
```

## Beacon chain state transition function

### Epoch processing

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    # Run before registry and after finality updates
    process_pending_deposits(state)  # [New in DepositsEIP]
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_roots_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
```

#### Helper functions

##### New `get_validator_from_indexed_deposit_data`

```python
def get_validator_from_indexed_deposit_data(indexed_deposit_data: IndexedDepositData) -> Validator:
    amount = indexed_deposit_data.amount
    effective_balance = min(amount - amount % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE)

    return Validator(
        pubkey=indexed_deposit_data.pubkey,
        withdrawal_credentials=indexed_deposit_data.withdrawal_credentials,
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
        effective_balance=effective_balance,
    )
```

##### New `apply_pending_deposit`

```python
def apply_pending_deposit(state: BeaconState, indexed_deposit_data: IndexedDepositData) -> None:
    pubkey = indexed_deposit_data.pubkey
    amount = indexed_deposit_data.amount
    validator_pubkeys = [v.pubkey for v in state.validators]
    if pubkey not in validator_pubkeys:
        # Add validator and balance entries
        state.validators.append(get_validator_from_indexed_deposit_data(indexed_deposit_data))
        state.balances.append(amount)
    else:
        # Increase balance by deposit amount
        index = ValidatorIndex(validator_pubkeys.index(pubkey))
        increase_balance(state, index, amount)
```

#### New `process_pending_deposits`

```python
def process_pending_deposits(state: BeaconState) -> None:
    finalized_epoch = state.finalized_checkpoint.epoch

    next_pending_deposit_index = 0
    for pending_deposit in state.pending_deposits:
        # Preserve deposits per epoch boundary
        if next_pending_deposit_index >= MAX_DEPOSITS * SLOTS_PER_EPOCH:
            break

        # Apply only finalized deposits
        if pending_deposit.epoch > finalized_epoch:
            break

        # Skip already applied deposits
        if pending_deposit.index >= state.eth1_deposit_index:
            apply_pending_deposit(state, pending_deposit)
            state.eth1_deposit_index += 1

        next_pending_deposit_index += 1

    state.pending_deposit = state.pending_deposit[next_pending_deposit_index:]
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    if is_execution_enabled(state, block.body):
        process_withdrawals(state, block.body.execution_payload)
        process_execution_payload(state, block.body.execution_payload, EXECUTION_ENGINE)  # [Modified in DepositsEIP]
        process_deposit_receipts(state, block.body.execution_payload)  # [New in DepositsEIP]
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)  # [Modified in DepositsEIP]
    process_sync_aggregate(state, block.body.sync_aggregate)
```
        
#### New `process_deposit_receipts`

```python
def process_deposit_receipts(state: BeaconState, payload: ExecutionPayload) -> None:
    current_epoch = get_current_epoch(state)

    for deposit_receipt in payload.deposit_receipts:
        if pubkey not in validator_pubkeys:
            # Verify the deposit signature (proof of possession) which is not checked by the deposit contract
            deposit_message = DepositMessage(
                pubkey=deposit_receipt.pubkey,
                withdrawal_credentials=deposit_receipt.withdrawal_credentials,
                amount=deposit_receipt.amount,
            )
            domain = compute_domain(DOMAIN_DEPOSIT)  # Fork-agnostic domain since deposits are valid across forks
            signing_root = compute_signing_root(deposit_message, domain)
            if not bls.Verify(pubkey, signing_root, deposit.data.signature):
                continue

        pending_deposit = IndexedDepositData(
            pubkey=deposit_receipt.pubkey,
            withdrawal_credentials=deposit_receipt.withdrawal_credentials,
            amount=deposit_receipt.amount,
            index=deposit_receipt.index,
            epoch=current_epoch,
        )
        state.pending_deposits.append(pending_deposit)
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
        withdrawals_root=hash_tree_root(payload.withdrawals),
        deposit_receipts_root=hash_tree_root(payload.deposit_receipts),  # [New in DepositsEIP]
    )
```

#### Modified `process_operations`

*Note*: The function `process_operations` is modified to process `BLSToExecutionChange` operations included in the block.

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # Verify that outstanding deposits are processed up to the maximum number of deposits
    unprocessed_deposits_count = max(0, state.eth1_data.deposit_count - state.eth1_deposit_index)  # [New in DepositsEIP]
    assert len(body.deposits) == min(MAX_DEPOSITS, unprocessed_deposits_count)  # [Modified in DepositsEIP]

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

## Testing

*Note*: The function `initialize_beacon_state_from_eth1` is modified for pure DepositsEIP testing only.
Modifications include:
1. Use `DEPOSITS_EIP_FORK_VERSION` as the previous and current fork version.
2. Utilize the DepositsEIP `BeaconBlockBody` when constructing the initial `latest_block_header`.

```python
def initialize_beacon_state_from_eth1(eth1_block_hash: Hash32,
                                      eth1_timestamp: uint64,
                                      deposits: Sequence[Deposit],
                                      execution_payload_header: ExecutionPayloadHeader=ExecutionPayloadHeader()
                                      ) -> BeaconState:
    fork = Fork(
        previous_version=CAPELLA_FORK_VERSION,  # [Modified in Capella] for testing only
        current_version=CAPELLA_FORK_VERSION,  # [Modified in Capella]
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
