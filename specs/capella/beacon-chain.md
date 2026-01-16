# Capella -- The Beacon Chain

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
  - [Domains](#domains)
- [Preset](#preset)
  - [Max operations per block](#max-operations-per-block)
  - [Execution](#execution)
  - [Withdrawals processing](#withdrawals-processing)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`Withdrawal`](#withdrawal)
    - [`BLSToExecutionChange`](#blstoexecutionchange)
    - [`SignedBLSToExecutionChange`](#signedblstoexecutionchange)
    - [`HistoricalSummary`](#historicalsummary)
  - [Modified containers](#modified-containers)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
- [Dataclasses](#dataclasses)
  - [New dataclasses](#new-dataclasses)
    - [`ExpectedWithdrawals`](#expectedwithdrawals)
- [Helpers](#helpers)
  - [Predicates](#predicates)
    - [`has_eth1_withdrawal_credential`](#has_eth1_withdrawal_credential)
    - [`is_fully_withdrawable_validator`](#is_fully_withdrawable_validator)
    - [`is_partially_withdrawable_validator`](#is_partially_withdrawable_validator)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Historical summaries updates](#historical-summaries-updates)
  - [Block processing](#block-processing)
    - [New `get_balance_after_withdrawals`](#new-get_balance_after_withdrawals)
    - [New `get_validators_sweep_withdrawals`](#new-get_validators_sweep_withdrawals)
    - [New `get_expected_withdrawals`](#new-get_expected_withdrawals)
    - [New `apply_withdrawals`](#new-apply_withdrawals)
    - [New `update_next_withdrawal_index`](#new-update_next_withdrawal_index)
    - [New `update_next_withdrawal_validator_index`](#new-update_next_withdrawal_validator_index)
    - [New `process_withdrawals`](#new-process_withdrawals)
    - [Modified `process_execution_payload`](#modified-process_execution_payload)
    - [Modified `process_operations`](#modified-process_operations)
    - [New `process_bls_to_execution_change`](#new-process_bls_to_execution_change)

<!-- mdformat-toc end -->

## Introduction

Capella is a consensus-layer upgrade containing a number of features related to
validator withdrawals. Including:

- Automatic withdrawals of `withdrawable` validators.
- Partial withdrawals sweep for validators with 0x01 withdrawal credentials and
  balances in excess of `MAX_EFFECTIVE_BALANCE`.
- Operation to change from `BLS_WITHDRAWAL_PREFIX` to
  `ETH1_ADDRESS_WITHDRAWAL_PREFIX` versioned withdrawal credentials to enable
  withdrawals for a validator.

Another new feature is the new independent state and block historical
accumulators that replace the original singular historical roots. With these
accumulators, it becomes possible to validate the entire block history that led
up to that particular state without any additional information beyond the state
and the blocks.

## Custom types

We define the following Python custom types for type hinting and readability:

| Name              | SSZ equivalent | Description                |
| ----------------- | -------------- | -------------------------- |
| `WithdrawalIndex` | `uint64`       | an index of a `Withdrawal` |

### Domains

| Name                             | Value                      |
| -------------------------------- | -------------------------- |
| `DOMAIN_BLS_TO_EXECUTION_CHANGE` | `DomainType('0x0A000000')` |

## Preset

### Max operations per block

| Name                           | Value         |
| ------------------------------ | ------------- |
| `MAX_BLS_TO_EXECUTION_CHANGES` | `2**4` (= 16) |

### Execution

| Name                          | Value                 | Description                                           |
| ----------------------------- | --------------------- | ----------------------------------------------------- |
| `MAX_WITHDRAWALS_PER_PAYLOAD` | `uint64(2**4)` (= 16) | Maximum amount of withdrawals allowed in each payload |

### Withdrawals processing

| Name                                   | Value              |
| -------------------------------------- | ------------------ |
| `MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP` | `2**14` (= 16,384) |

## Containers

### New containers

#### `Withdrawal`

```python
class Withdrawal(Container):
    index: WithdrawalIndex
    validator_index: ValidatorIndex
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

#### `HistoricalSummary`

*Note*: `HistoricalSummary` matches the components of the phase0
`HistoricalBatch` making the two \*hash_tree_root-compatible.

```python
class HistoricalSummary(Container):
    block_summary_root: Root
    state_summary_root: Root
```

### Modified containers

#### `ExecutionPayload`

```python
class ExecutionPayload(Container):
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
    block_hash: Hash32
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    # [New in Capella]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
```

#### `ExecutionPayloadHeader`

```python
class ExecutionPayloadHeader(Container):
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
    block_hash: Hash32
    transactions_root: Root
    # [New in Capella]
    withdrawals_root: Root
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    execution_payload: ExecutionPayload
    # [New in Capella]
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
```

#### `BeaconState`

*Note*: `historical_roots` is frozen in Capella and is replaced by
`historical_summaries`.

```python
class BeaconState(Container):
    genesis_time: uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH]
    eth1_deposit_index: uint64
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    randao_mixes: Vector[Bytes32, EPOCHS_PER_HISTORICAL_VECTOR]
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]
    previous_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    current_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    inactivity_scores: List[uint64, VALIDATOR_REGISTRY_LIMIT]
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # [Modified in Capella]
    latest_execution_payload_header: ExecutionPayloadHeader
    # [New in Capella]
    next_withdrawal_index: WithdrawalIndex
    # [New in Capella]
    next_withdrawal_validator_index: ValidatorIndex
    # [New in Capella]
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
```

## Dataclasses

### New dataclasses

#### `ExpectedWithdrawals`

```python
@dataclass
class ExpectedWithdrawals(object):
    withdrawals: Sequence[Withdrawal]
    processed_sweep_withdrawals_count: uint64
```

## Helpers

### Predicates

#### `has_eth1_withdrawal_credential`

```python
def has_eth1_withdrawal_credential(validator: Validator) -> bool:
    """
    Check if ``validator`` has an 0x01 prefixed "eth1" withdrawal credential.
    """
    return validator.withdrawal_credentials[:1] == ETH1_ADDRESS_WITHDRAWAL_PREFIX
```

#### `is_fully_withdrawable_validator`

```python
def is_fully_withdrawable_validator(validator: Validator, balance: Gwei, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is fully withdrawable.
    """
    return (
        has_eth1_withdrawal_credential(validator)
        and validator.withdrawable_epoch <= epoch
        and balance > 0
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
    return (
        has_eth1_withdrawal_credential(validator)
        and has_max_effective_balance
        and has_excess_balance
    )
```

## Beacon chain state transition function

### Epoch processing

*Note*: The function `process_historical_summaries_update` replaces
`process_historical_roots_update` in Capella.

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
    # [Modified in Capella]
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
```

#### Historical summaries updates

```python
def process_historical_summaries_update(state: BeaconState) -> None:
    # Set historical block root accumulator.
    next_epoch = Epoch(get_current_epoch(state) + 1)
    if next_epoch % (SLOTS_PER_HISTORICAL_ROOT // SLOTS_PER_EPOCH) == 0:
        historical_summary = HistoricalSummary(
            block_summary_root=hash_tree_root(state.block_roots),
            state_summary_root=hash_tree_root(state.state_roots),
        )
        state.historical_summaries.append(historical_summary)
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    # [Modified in Capella]
    # Removed `is_execution_enabled` call
    # [New in Capella]
    process_withdrawals(state, block.body.execution_payload)
    # [Modified in Capella]
    process_execution_payload(state, block.body, EXECUTION_ENGINE)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    # [Modified in Capella]
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### New `get_balance_after_withdrawals`

```python
def get_balance_after_withdrawals(
    state: BeaconState,
    validator_index: ValidatorIndex,
    withdrawals: Sequence[Withdrawal],
) -> Gwei:
    withdrawn = sum(
        withdrawal.amount
        for withdrawal in withdrawals
        if withdrawal.validator_index == validator_index
    )
    return state.balances[validator_index] - withdrawn
```

#### New `get_validators_sweep_withdrawals`

```python
def get_validators_sweep_withdrawals(
    state: BeaconState,
    withdrawal_index: WithdrawalIndex,
    prior_withdrawals: Sequence[Withdrawal],
) -> Tuple[Sequence[Withdrawal], WithdrawalIndex, uint64]:
    epoch = get_current_epoch(state)
    validators_limit = min(len(state.validators), MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
    withdrawals_limit = MAX_WITHDRAWALS_PER_PAYLOAD
    # There must be at least one space reserved for validator sweep withdrawals
    assert len(prior_withdrawals) < withdrawals_limit

    processed_count: uint64 = 0
    withdrawals: List[Withdrawal] = []
    validator_index = state.next_withdrawal_validator_index
    for _ in range(validators_limit):
        all_withdrawals = prior_withdrawals + withdrawals
        has_reached_limit = len(all_withdrawals) >= withdrawals_limit
        if has_reached_limit:
            break

        validator = state.validators[validator_index]
        balance = get_balance_after_withdrawals(state, validator_index, all_withdrawals)
        if is_fully_withdrawable_validator(validator, balance, epoch):
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    amount=balance,
                )
            )
            withdrawal_index += WithdrawalIndex(1)
        elif is_partially_withdrawable_validator(validator, balance):
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    amount=balance - MAX_EFFECTIVE_BALANCE,
                )
            )
            withdrawal_index += WithdrawalIndex(1)

        validator_index = ValidatorIndex((validator_index + 1) % len(state.validators))
        processed_count += 1

    return withdrawals, withdrawal_index, processed_count
```

#### New `get_expected_withdrawals`

```python
def get_expected_withdrawals(state: BeaconState) -> ExpectedWithdrawals:
    withdrawal_index = state.next_withdrawal_index
    withdrawals: List[Withdrawal] = []

    # Get validators sweep withdrawals
    validators_sweep_withdrawals, withdrawal_index, processed_validators_sweep_count = (
        get_validators_sweep_withdrawals(state, withdrawal_index, withdrawals)
    )
    withdrawals.extend(validators_sweep_withdrawals)

    return ExpectedWithdrawals(
        withdrawals,
        processed_validators_sweep_count,
    )
```

#### New `apply_withdrawals`

```python
def apply_withdrawals(state: BeaconState, withdrawals: Sequence[Withdrawal]) -> None:
    for withdrawal in withdrawals:
        decrease_balance(state, withdrawal.validator_index, withdrawal.amount)
```

#### New `update_next_withdrawal_index`

```python
def update_next_withdrawal_index(state: BeaconState, withdrawals: Sequence[Withdrawal]) -> None:
    # Update the next withdrawal index if this block contained withdrawals
    if len(withdrawals) != 0:
        latest_withdrawal = withdrawals[-1]
        state.next_withdrawal_index = WithdrawalIndex(latest_withdrawal.index + 1)
```

#### New `update_next_withdrawal_validator_index`

```python
def update_next_withdrawal_validator_index(
    state: BeaconState, withdrawals: Sequence[Withdrawal]
) -> None:
    # Update the next validator index to start the next withdrawal sweep
    if len(withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
        # Next sweep starts after the latest withdrawal's validator index
        next_validator_index = ValidatorIndex(
            (withdrawals[-1].validator_index + 1) % len(state.validators)
        )
        state.next_withdrawal_validator_index = next_validator_index
    else:
        # Advance sweep by the max length of the sweep if there was not a full set of withdrawals
        next_index = state.next_withdrawal_validator_index + MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
        next_validator_index = ValidatorIndex(next_index % len(state.validators))
        state.next_withdrawal_validator_index = next_validator_index
```

#### New `process_withdrawals`

```python
def process_withdrawals(state: BeaconState, payload: ExecutionPayload) -> None:
    # Get expected withdrawals
    expected = get_expected_withdrawals(state)
    assert payload.withdrawals == expected.withdrawals

    # Apply expected withdrawals
    apply_withdrawals(state, expected.withdrawals)

    # Update withdrawals fields in the state
    update_next_withdrawal_index(state, expected.withdrawals)
    update_next_withdrawal_validator_index(state, expected.withdrawals)
```

#### Modified `process_execution_payload`

*Note*: The function `process_execution_payload` is modified to use the new
`ExecutionPayloadHeader` type and removed the `is_merge_transition_complete`
check.

```python
def process_execution_payload(
    state: BeaconState, body: BeaconBlockBody, execution_engine: ExecutionEngine
) -> None:
    payload = body.execution_payload
    # [Modified in Capella]
    # Removed `is_merge_transition_complete` check
    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_time_at_slot(state, state.slot)
    # Verify the execution payload is valid
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(execution_payload=payload)
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
        # [New in Capella]
        withdrawals_root=hash_tree_root(payload.withdrawals),
    )
```

#### Modified `process_operations`

*Note*: The function `process_operations` is modified to process
`BLSToExecutionChange` operations included in the block.

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # Verify that outstanding deposits are processed up to the maximum number of deposits
    assert len(body.deposits) == min(
        MAX_DEPOSITS, state.eth1_data.deposit_count - state.eth1_deposit_index
    )

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    # [New in Capella]
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
```

#### New `process_bls_to_execution_change`

```python
def process_bls_to_execution_change(
    state: BeaconState, signed_address_change: SignedBLSToExecutionChange
) -> None:
    address_change = signed_address_change.message

    assert address_change.validator_index < len(state.validators)

    validator = state.validators[address_change.validator_index]

    assert validator.withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX
    assert validator.withdrawal_credentials[1:] == hash(address_change.from_bls_pubkey)[1:]

    # Fork-agnostic domain since address changes are valid across forks
    domain = compute_domain(
        DOMAIN_BLS_TO_EXECUTION_CHANGE, genesis_validators_root=state.genesis_validators_root
    )
    signing_root = compute_signing_root(address_change, domain)
    assert bls.Verify(address_change.from_bls_pubkey, signing_root, signed_address_change.signature)

    validator.withdrawal_credentials = (
        ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + address_change.to_execution_address
    )
```
