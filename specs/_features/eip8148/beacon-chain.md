# EIP-8148 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `SweepThresholdRequests`](#new-sweepthresholdrequests)
  - [New `SweepThresholds`](#new-sweepthresholds)
- [Constants](#constants)
  - [New execution layer triggered request type](#new-execution-layer-triggered-request-type)
  - [Sweep threshold validation](#sweep-threshold-validation)
- [Preset](#preset)
  - [Execution](#execution)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`BeaconState`](#beaconstate)
    - [`ExecutionRequests`](#executionrequests)
  - [New containers](#new-containers)
    - [`SetSweepThresholdRequest`](#setsweepthresholdrequest)
- [Helper functions](#helper-functions)
  - [Predicates](#predicates)
    - [Modified `is_partially_withdrawable_validator`](#modified-is_partially_withdrawable_validator)
  - [Misc](#misc)
    - [New `get_effective_sweep_threshold`](#new-get_effective_sweep_threshold)
  - [Validator registry](#validator-registry)
    - [Modified `add_validator_to_registry`](#modified-add_validator_to_registry)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Modified `get_execution_requests_list`](#modified-get_execution_requests_list)
    - [Withdrawals](#withdrawals)
      - [Modified `get_validators_sweep_withdrawals`](#modified-get_validators_sweep_withdrawals)
    - [Operations](#operations)
      - [New `process_set_sweep_threshold_request`](#new-process_set_sweep_threshold_request)
    - [Parent execution payload](#parent-execution-payload)
      - [Modified `apply_parent_execution_payload`](#modified-apply_parent_execution_payload)

<!-- mdformat-toc end -->

## Introduction

This upgrade adds custom validator sweep threshold functionality to the beacon
chain as part of the EIP-8148 upgrade.

This document specifies the beacon chain changes required to support these
custom thresholds. The upgrade introduces a new request type within the
execution payload, triggered by execution layer transactions, which updates a
validator's sweep configuration in the beacon state. This allows validators to
control their balance withdrawals more precisely.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Types

### New `SweepThresholdRequests`

```python
class SweepThresholdRequests(ProgressiveList[SetSweepThresholdRequest]):
    pass
```

### New `SweepThresholds`

```python
class SweepThresholds(ProgressiveList[Gwei]):
    pass
```

## Constants

### New execution layer triggered request type

| Name                           | Value            |
| ------------------------------ | ---------------- |
| `SWEEP_THRESHOLD_REQUEST_TYPE` | `Bytes1('0x05')` |

### Sweep threshold validation

| Name                  | Value                                         |
| --------------------- | --------------------------------------------- |
| `MIN_SWEEP_THRESHOLD` | `MIN_ACTIVATION_BALANCE + Gwei(2**0 * 10**9)` |

## Preset

### Execution

| Name                                           | Value                 | Description                                                                                       |
| ---------------------------------------------- | --------------------- | ------------------------------------------------------------------------------------------------- |
| `MAX_SET_SWEEP_THRESHOLD_REQUESTS_PER_PAYLOAD` | `Uint64(2**4)` (= 16) | *[New in EIP8148]* Maximum number of execution layer set sweep threshold requests in each payload |

## Containers

### Modified containers

#### `BeaconState`

```python
class BeaconState(ProgressiveContainer(active_fields=[1] * 47)):
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
    latest_block_hash: Hash32
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
    proposer_lookahead: ProposerLookahead
    builders: Builders
    next_withdrawal_builder_index: BuilderIndex
    execution_payload_availability: ExecutionPayloadAvailability
    builder_pending_payments: BuilderPendingPayments
    builder_pending_withdrawals: BuilderPendingWithdrawals
    latest_execution_payload_bid: ExecutionPayloadBid
    payload_expected_withdrawals: Withdrawals
    ptc_window: PTCWindow
    # [New in EIP8148]
    validator_sweep_thresholds: SweepThresholds
```

#### `ExecutionRequests`

```python
class ExecutionRequests(ProgressiveContainer(active_fields=[1] * 6)):
    deposits: DepositRequests
    withdrawals: WithdrawalRequests
    consolidations: ConsolidationRequests
    builder_deposits: BuilderDepositRequests
    builder_exits: BuilderExitRequests
    # [New in EIP8148]
    sweep_thresholds: SweepThresholdRequests
```

### New containers

#### `SetSweepThresholdRequest`

```python
class SetSweepThresholdRequest(Container):
    source_address: ExecutionAddress
    validator_pubkey: BLSPubkey
    threshold: Gwei
```

## Helper functions

### Predicates

#### Modified `is_partially_withdrawable_validator`

```python
def is_partially_withdrawable_validator(
    validator: Validator, balance: Gwei, sweep_threshold: Gwei
) -> bool:
    """
    Check if ``validator`` is partially withdrawable.
    """
    # [Modified in EIP8148]
    effective_sweep_threshold = get_effective_sweep_threshold(validator, sweep_threshold)
    # [Modified in EIP8148]
    has_effective_sweep_threshold = validator.effective_balance >= effective_sweep_threshold
    # [Modified in EIP8148]
    has_excess_balance = balance > effective_sweep_threshold
    return (
        has_execution_withdrawal_credential(validator)
        # [Modified in EIP8148]
        and has_effective_sweep_threshold
        and has_excess_balance
    )
```

### Misc

#### New `get_effective_sweep_threshold`

```python
def get_effective_sweep_threshold(validator: Validator, sweep_threshold: Gwei) -> Gwei:
    """
    Get effective sweep threshold for ``validator``.
    """
    if sweep_threshold != 0:
        return sweep_threshold
    else:
        return get_max_effective_balance(validator)
```

### Validator registry

#### Modified `add_validator_to_registry`

*Note*: The function `add_validator_to_registry` is modified to initialize the
item in the `validator_sweep_thresholds` list.

```python
def add_validator_to_registry(
    state: BeaconState, pubkey: BLSPubkey, withdrawal_credentials: Bytes32, amount: Uint64
) -> None:
    index = get_index_for_new_validator(state)
    validator = get_validator_from_deposit(pubkey, withdrawal_credentials, amount)
    set_or_append_list(state.validators, index, validator)
    set_or_append_list(state.balances, index, amount)
    set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.inactivity_scores, index, Uint64(0))
    # [New in EIP8148]
    set_or_append_list(
        state.validator_sweep_thresholds,
        index,
        MAX_EFFECTIVE_BALANCE_ELECTRA
        if has_compounding_withdrawal_credential(validator)
        else Gwei(0),
    )
```

## Beacon chain state transition function

### Block processing

#### Execution payload

##### Modified `get_execution_requests_list`

*Note*: Encodes execution requests as defined by
[EIP-7685](https://eips.ethereum.org/EIPS/eip-7685).

```python
def get_execution_requests_list(execution_requests: ExecutionRequests) -> Sequence[bytes]:
    requests: Sequence[Tuple[Bytes1, ProgressiveList]] = [
        (DEPOSIT_REQUEST_TYPE, execution_requests.deposits),
        (WITHDRAWAL_REQUEST_TYPE, execution_requests.withdrawals),
        (CONSOLIDATION_REQUEST_TYPE, execution_requests.consolidations),
        (BUILDER_DEPOSIT_REQUEST_TYPE, execution_requests.builder_deposits),
        (BUILDER_EXIT_REQUEST_TYPE, execution_requests.builder_exits),
        # [New in EIP8148]
        (SWEEP_THRESHOLD_REQUEST_TYPE, execution_requests.sweep_thresholds),
    ]

    return [
        request_type + ssz_serialize(request_data)
        for request_type, request_data in requests
        if len(request_data) != 0
    ]
```

#### Withdrawals

##### Modified `get_validators_sweep_withdrawals`

```python
def get_validators_sweep_withdrawals(
    state: BeaconState,
    withdrawal_index: WithdrawalIndex,
    prior_withdrawals: Sequence[Withdrawal],
) -> Tuple[Sequence[Withdrawal], WithdrawalIndex, Uint64]:
    epoch = get_current_epoch(state)
    validators_limit = min(len(state.validators), MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
    withdrawals_limit = MAX_WITHDRAWALS_PER_PAYLOAD
    # There must be at least one space reserved for validator sweep withdrawals
    assert len(prior_withdrawals) < withdrawals_limit

    processed_count: Uint64 = 0
    withdrawals: List[Withdrawal] = []
    validator_index = state.next_withdrawal_validator_index
    for _ in range(validators_limit):
        all_withdrawals = prior_withdrawals + withdrawals
        has_reached_limit = len(all_withdrawals) >= withdrawals_limit
        if has_reached_limit:
            break

        validator = state.validators[validator_index]
        balance = get_balance_after_withdrawals(state, validator_index, all_withdrawals)
        # [New in EIP8148]
        sweep_threshold = state.validator_sweep_thresholds[validator_index]
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
        # [Modified in EIP8148]
        elif is_partially_withdrawable_validator(validator, balance, sweep_threshold):
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    # [Modified in EIP8148]
                    amount=balance - get_effective_sweep_threshold(validator, sweep_threshold),
                )
            )
            withdrawal_index += WithdrawalIndex(1)

        validator_index = ValidatorIndex((validator_index + 1) % len(state.validators))
        processed_count += 1

    return withdrawals, withdrawal_index, processed_count
```

#### Operations

##### New `process_set_sweep_threshold_request`

*Note*: A request is rejected if its threshold is below the validator's current
balance. This prevents validators from gaming the sweep cycle to bypass the
partial withdrawal queue and perform immediate withdrawals. To lower a
threshold, validators must first request a partial withdrawal, wait for
processing, then set the desired threshold.

```python
def process_set_sweep_threshold_request(
    state: BeaconState, request: SetSweepThresholdRequest
) -> None:
    validator_pubkeys = [v.pubkey for v in state.validators]
    if request.validator_pubkey not in validator_pubkeys:
        return

    index = ValidatorIndex(validator_pubkeys.index(request.validator_pubkey))
    validator = state.validators[index]

    if not has_compounding_withdrawal_credential(validator):
        return
    if validator.withdrawal_credentials[12:] != request.source_address:
        return
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return
    if state.validator_sweep_thresholds[index] == request.threshold:
        return
    if request.threshold < state.balances[index]:
        return
    if request.threshold % EFFECTIVE_BALANCE_INCREMENT != 0:
        return
    if request.threshold < MIN_SWEEP_THRESHOLD:
        return
    if request.threshold > MAX_EFFECTIVE_BALANCE_ELECTRA:
        return

    state.validator_sweep_thresholds[index] = request.threshold
```

#### Parent execution payload

##### Modified `apply_parent_execution_payload`

*Note*: This function processes the parent's execution requests, queues the
builder payment, updates payload availability, and updates the latest block
hash. It is called by `process_parent_execution_payload` during block processing
and by the validator during block production before computing withdrawals.

```python
def apply_parent_execution_payload(
    state: BeaconState,
    requests: ExecutionRequests,
) -> None:
    parent_bid = state.latest_execution_payload_bid
    parent_slot = parent_bid.slot
    parent_epoch = compute_epoch_at_slot(parent_slot)

    assert len(requests.withdrawals) <= MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD
    assert len(requests.consolidations) <= MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
    assert len(requests.builder_deposits) <= MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD
    assert len(requests.builder_exits) <= MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD
    # [New in EIP8148]
    assert len(requests.sweep_thresholds) <= MAX_SET_SWEEP_THRESHOLD_REQUESTS_PER_PAYLOAD

    # Process execution requests from parent's payload. The execution
    # requests are processed at state.slot (child's slot), not the parent's slot.
    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(requests.deposits, process_deposit_request)
    for_ops(requests.withdrawals, process_withdrawal_request)
    for_ops(requests.consolidations, process_consolidation_request)
    for_ops(requests.builder_deposits, process_builder_deposit_request)
    for_ops(requests.builder_exits, process_builder_exit_request)
    # [New in EIP8148]
    for_ops(requests.sweep_thresholds, process_set_sweep_threshold_request)

    # Settle the builder payment
    if parent_epoch == get_current_epoch(state):
        payment_index = SLOTS_PER_EPOCH + parent_slot % SLOTS_PER_EPOCH
        settle_builder_payment(state, payment_index)
    elif parent_epoch == get_previous_epoch(state):
        payment_index = parent_slot % SLOTS_PER_EPOCH
        settle_builder_payment(state, payment_index)
    elif parent_bid.value > 0:
        # Parent is older than the previous epoch, its payment entry has been
        # evicted from builder_pending_payments. Append the withdrawal directly.
        state.builder_pending_withdrawals.append(
            BuilderPendingWithdrawal(
                fee_recipient=parent_bid.fee_recipient,
                amount=parent_bid.value,
                builder_index=parent_bid.builder_index,
            )
        )

    # Update parent payload availability and latest block hash
    state.execution_payload_availability[parent_slot % SLOTS_PER_HISTORICAL_ROOT] = 0b1
    state.latest_block_hash = parent_bid.block_hash
```
