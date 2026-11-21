# EIP-8148 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `SweepThresholdRequests`](#new-sweepthresholdrequests)
- [Constants](#constants)
  - [New execution layer triggered request type](#new-execution-layer-triggered-request-type)
  - [Sweep threshold encoding](#sweep-threshold-encoding)
- [Presets](#presets)
  - [Execution](#execution)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`ExecutionRequests`](#executionrequests)
  - [New containers](#new-containers)
    - [`SetSweepThresholdRequest`](#setsweepthresholdrequest)
- [Helper functions](#helper-functions)
  - [Math](#math)
    - [New `bytes_to_uint16`](#new-bytes_to_uint16)
  - [Misc](#misc)
    - [New `get_sweep_threshold`](#new-get_sweep_threshold)
    - [New `set_sweep_threshold`](#new-set_sweep_threshold)
  - [Predicates](#predicates)
    - [Modified `is_partially_withdrawable_validator`](#modified-is_partially_withdrawable_validator)
  - [Beacon state mutators](#beacon-state-mutators)
    - [Modified `switch_to_compounding_validator`](#modified-switch_to_compounding_validator)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_effective_balance_updates`](#modified-process_effective_balance_updates)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Modified `get_execution_requests_list`](#modified-get_execution_requests_list)
    - [Withdrawals](#withdrawals)
      - [Modified `get_validators_sweep_withdrawals`](#modified-get_validators_sweep_withdrawals)
    - [Deposits](#deposits)
      - [Modified `get_validator_from_deposit`](#modified-get_validator_from_deposit)
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
execution payload, triggered by execution layer transactions, which updates the
sweep threshold encoded in a validator's compounding withdrawal credentials.
This allows validators to control their balance withdrawals more precisely
without adding per-validator data to the beacon state.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Types

### New `SweepThresholdRequests`

```python
class SweepThresholdRequests(ProgressiveList[SetSweepThresholdRequest]):
    """
    The set-sweep-threshold requests pertaining to a single execution
    payload.
    """
```

## Constants

### New execution layer triggered request type

| Name                           | Value            |
| ------------------------------ | ---------------- |
| `SWEEP_THRESHOLD_REQUEST_TYPE` | `Bytes1("0x05")` |

### Sweep threshold encoding

| Name                                | Value       |
| ----------------------------------- | ----------- |
| `SWEEP_THRESHOLD_CREDENTIAL_OFFSET` | `Uint64(1)` |
| `SWEEP_THRESHOLD_CREDENTIAL_LENGTH` | `Uint64(2)` |

## Presets

### Execution

| Name                                           | Value                 | Description                                                                                       |
| ---------------------------------------------- | --------------------- | ------------------------------------------------------------------------------------------------- |
| `MAX_SET_SWEEP_THRESHOLD_REQUESTS_PER_PAYLOAD` | `Uint64(2**4)` (= 16) | *[New in EIP8148]* Maximum number of execution layer set sweep threshold requests in each payload |

## Containers

### Modified containers

#### `ExecutionRequests`

```python
class ExecutionRequests(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=6)

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

### Math

#### New `bytes_to_uint16`

```python
def bytes_to_uint16(data: bytes) -> Uint16:
    """
    Return the integer deserialization of ``data`` interpreted as ``ENDIANNESS``-endian.
    """
    return Uint16(int.from_bytes(data, ENDIANNESS))
```

### Misc

#### New `get_sweep_threshold`

A validator's sweep threshold is stored in its compounding withdrawal
credentials. The `SWEEP_THRESHOLD_CREDENTIAL_LENGTH` bytes starting at
`SWEEP_THRESHOLD_CREDENTIAL_OFFSET`, which are unused before this upgrade, hold
the threshold in units of `EFFECTIVE_BALANCE_INCREMENT`, encoded as a
little-endian integer:

| Bytes    | Contents                                         |
| -------- | ------------------------------------------------ |
| `0`      | `COMPOUNDING_WITHDRAWAL_PREFIX` (`0x02`)         |
| `1..2`   | Threshold in `EFFECTIVE_BALANCE_INCREMENT` units |
| `3..11`  | Reserved                                         |
| `12..31` | Execution address                                |

*Note*: A stored value of `0` means the default threshold,
`MAX_EFFECTIVE_BALANCE_ELECTRA`. A value that is out of range is read as the
default, so that credentials built by tooling unaware of this upgrade, or
carrying a nonsensical value, behave as they did before. For credentials with
any other prefix, the threshold is `get_max_effective_balance(validator)`.

```python
def get_sweep_threshold(validator: Validator) -> Gwei:
    """
    Get the sweep threshold of ``validator``.
    """
    if not has_compounding_withdrawal_credential(validator):
        return get_max_effective_balance(validator)

    start = SWEEP_THRESHOLD_CREDENTIAL_OFFSET
    end = start + SWEEP_THRESHOLD_CREDENTIAL_LENGTH
    increments = bytes_to_uint16(validator.withdrawal_credentials[start:end])
    threshold = Gwei(increments) * EFFECTIVE_BALANCE_INCREMENT

    if threshold < MIN_ACTIVATION_BALANCE:
        return MAX_EFFECTIVE_BALANCE_ELECTRA
    if threshold > MAX_EFFECTIVE_BALANCE_ELECTRA:
        return MAX_EFFECTIVE_BALANCE_ELECTRA

    return threshold
```

#### New `set_sweep_threshold`

*Note*: A threshold of `MAX_EFFECTIVE_BALANCE_ELECTRA` is stored as `0`, so that
every threshold has a single encoding and a validator that sets the maximum has
the same credentials as one that never set a threshold.

```python
def set_sweep_threshold(validator: Validator, threshold: Gwei) -> None:
    """
    Store ``threshold`` in the compounding withdrawal credentials of ``validator``.
    """
    increments = Uint16(0)
    if MIN_ACTIVATION_BALANCE <= threshold < MAX_EFFECTIVE_BALANCE_ELECTRA:
        increments = Uint16(threshold // EFFECTIVE_BALANCE_INCREMENT)

    start = SWEEP_THRESHOLD_CREDENTIAL_OFFSET
    end = start + SWEEP_THRESHOLD_CREDENTIAL_LENGTH
    credentials = validator.withdrawal_credentials
    validator.withdrawal_credentials = Bytes32(
        credentials[:start] + uint_to_bytes(increments) + credentials[end:]
    )
```

### Predicates

#### Modified `is_partially_withdrawable_validator`

```python
def is_partially_withdrawable_validator(validator: Validator, balance: Gwei) -> bool:
    """
    Check if ``validator`` is partially withdrawable.
    """
    # [Modified in EIP8148]
    sweep_threshold = get_sweep_threshold(validator)
    # [Modified in EIP8148]
    has_sweep_threshold = validator.effective_balance >= sweep_threshold
    # [Modified in EIP8148]
    has_excess_balance = balance > sweep_threshold
    return (
        has_execution_withdrawal_credential(validator)
        # [Modified in EIP8148]
        and has_sweep_threshold
        and has_excess_balance
    )
```

### Beacon state mutators

#### Modified `switch_to_compounding_validator`

*Note*: The threshold bytes are cleared so that a validator switching to
compounding credentials starts at the default threshold.

```python
def switch_to_compounding_validator(state: BeaconState, index: ValidatorIndex) -> None:
    validator = state.validators[index]
    validator.withdrawal_credentials = Bytes32(
        COMPOUNDING_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]
    )
    # [New in EIP8148]
    set_sweep_threshold(validator, MAX_EFFECTIVE_BALANCE_ELECTRA)
    queue_excess_active_balance(state, index)
```

## Beacon chain state transition function

### Epoch processing

#### Modified `process_effective_balance_updates`

*Note*: The function `process_effective_balance_updates` is modified to use
custom sweep thresholds.

```python
def process_effective_balance_updates(state: BeaconState) -> None:
    # Update effective balances with hysteresis
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        HYSTERESIS_INCREMENT = Uint64(EFFECTIVE_BALANCE_INCREMENT // HYSTERESIS_QUOTIENT)
        DOWNWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_DOWNWARD_MULTIPLIER
        UPWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_UPWARD_MULTIPLIER
        # [Modified in EIP8148]
        sweep_threshold = get_sweep_threshold(validator)

        if (
            balance + DOWNWARD_THRESHOLD < validator.effective_balance
            or validator.effective_balance + UPWARD_THRESHOLD < balance
        ):
            # [Modified in EIP8148]
            validator.effective_balance = min(
                balance - balance % EFFECTIVE_BALANCE_INCREMENT, sweep_threshold
            )
```

### Block processing

#### Execution payload

##### Modified `get_execution_requests_list`

*Note*: Encodes execution requests as defined by
[EIP-7685](https://eips.ethereum.org/EIPS/eip-7685).

```python
def get_execution_requests_list(execution_requests: ExecutionRequests) -> Sequence[bytes]:
    requests: Sequence[tuple[Bytes1, ProgressiveList]] = [
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
) -> tuple[Sequence[Withdrawal], WithdrawalIndex, Uint64]:
    epoch = get_current_epoch(state)
    validators_limit = min(len(state.validators), MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
    withdrawals_limit = MAX_WITHDRAWALS_PER_PAYLOAD
    # There must be at least one space reserved for validator sweep withdrawals
    assert len(prior_withdrawals) < withdrawals_limit

    processed_count = Uint64(0)
    withdrawals: list[Withdrawal] = []
    validator_index = state.next_withdrawal_validator_index
    for _ in range(validators_limit):
        all_withdrawals = list(prior_withdrawals) + withdrawals
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
            withdrawal_index += 1
        elif is_partially_withdrawable_validator(validator, balance):
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    # [Modified in EIP8148]
                    amount=balance - get_sweep_threshold(validator),
                )
            )
            withdrawal_index += 1

        validator_index = (validator_index + 1) % len(state.validators)
        processed_count += 1

    return withdrawals, withdrawal_index, processed_count
```

#### Deposits

##### Modified `get_validator_from_deposit`

*Note*: The function `get_validator_from_deposit` is modified to store the
threshold of a new compounding validator in its canonical encoding, and to cap
its initial effective balance at that threshold.

```python
def get_validator_from_deposit(
    pubkey: BLSPubkey, withdrawal_credentials: Bytes32, amount: Gwei
) -> Validator:
    validator = Validator(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        effective_balance=Gwei(0),
        slashed=Boolean(False),
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
    )

    # [New in EIP8148]
    if has_compounding_withdrawal_credential(validator):
        set_sweep_threshold(validator, get_sweep_threshold(validator))

    # [Modified in EIP8148]
    sweep_threshold = get_sweep_threshold(validator)
    validator.effective_balance = min(
        amount - amount % EFFECTIVE_BALANCE_INCREMENT, sweep_threshold
    )

    return validator
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
    validator_pubkeys = [validator.pubkey for validator in state.validators]
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
    if get_sweep_threshold(validator) == request.threshold:
        return
    if request.threshold < state.balances[index]:
        return
    if request.threshold % EFFECTIVE_BALANCE_INCREMENT != 0:
        return
    if request.threshold < MIN_ACTIVATION_BALANCE:
        return
    if request.threshold > MAX_EFFECTIVE_BALANCE_ELECTRA:
        return

    set_sweep_threshold(validator, request.threshold)
```

#### Parent execution payload

##### Modified `apply_parent_execution_payload`

*Note*: This function queues the builder payment, processes the parent's
execution requests, updates payload availability, and updates the latest block
hash. It is called by `process_parent_execution_payload` during block processing
and by the validator during block production before computing withdrawals.

```python
def apply_parent_execution_payload(
    state: BeaconState,
    requests: ExecutionRequests,
) -> None:
    parent_bid = state.latest_execution_payload_bid
    parent_slot = state.latest_block_header.slot
    parent_epoch = compute_epoch_at_slot(parent_slot)

    assert len(requests.withdrawals) <= MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD
    assert len(requests.consolidations) <= MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
    assert len(requests.builder_deposits) <= MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD
    assert len(requests.builder_exits) <= MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD
    # [New in EIP8148]
    assert len(requests.sweep_thresholds) <= MAX_SET_SWEEP_THRESHOLD_REQUESTS_PER_PAYLOAD

    # Settle the builder payment before the requests so that a builder exit
    # request is rejected while the payment is pending
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

    # Update parent payload availability and latest block hash
    state.execution_payload_availability[parent_slot % SLOTS_PER_HISTORICAL_ROOT] = Boolean(True)
    state.latest_block_hash = parent_bid.block_hash
```
