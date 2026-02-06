# EIP8148 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
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
    - [Withdrawals](#withdrawals)
      - [Modified `get_validators_sweep_withdrawals`](#modified-get_validators_sweep_withdrawals)
    - [Execution payload](#execution-payload)
      - [Modified `get_execution_requests_list`](#modified-get_execution_requests_list)
    - [Operations](#operations)
      - [New `process_set_sweep_threshold_request`](#new-process_set_sweep_threshold_request)
  - [Execution payload processing](#execution-payload-processing)
    - [Modified `process_execution_payload`](#modified-process_execution_payload)
- [Testing](#testing)

<!-- mdformat-toc end -->

## Introduction

This upgrade adds custom validator sweep threshold functionality to the beacon chain as part of the eip8148 upgrade.

This document specifies the beacon chain changes required to support these custom thresholds. The upgrade introduces a new request type within the execution payload, triggered by execution layer transactions, which updates a validator's sweep configuration in the beacon state. This allows validators to control their balance withdrawals more precisely.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md).

## Constants

### New execution layer triggered request type

| Name                           | Value            |
| ----------------------------   | ---------------- |
| `SWEEP_THRESHOLD_REQUEST_TYPE` | `Bytes1('0x03')` |

### Sweep threshold validation

| Name                        | Value                                         |
| --------------------------- | --------------------------------------------- |
| `MIN_SWEEP_THRESHOLD`       | `MIN_ACTIVATION_BALANCE + Gwei(2**0 * 10**9)` |

## Preset

### Execution

| Name                                           | Value                     | Description                                                                                         |
| ----------------------------------------       | ------------------------- | --------------------------------------------------------------------------------------------------- |
| `MAX_SET_SWEEP_THRESHOLD_REQUESTS_PER_PAYLOAD` | `uint64(2**4)` (= 16)     | *[New in eip8148]* Maximum number of execution layer set sweep threshold requests in each payload   |

## Containers

### Modified containers

#### `BeaconState`

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
    latest_execution_payload_bid: ExecutionPayloadBid
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
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
    proposer_lookahead: Vector[ValidatorIndex, (MIN_SEED_LOOKAHEAD + 1) * SLOTS_PER_EPOCH]
    builders: List[Builder, BUILDER_REGISTRY_LIMIT]
    next_withdrawal_builder_index: BuilderIndex
    execution_payload_availability: Bitvector[SLOTS_PER_HISTORICAL_ROOT]
    builder_pending_payments: Vector[BuilderPendingPayment, 2 * SLOTS_PER_EPOCH]
    builder_pending_withdrawals: List[BuilderPendingWithdrawal, BUILDER_PENDING_WITHDRAWALS_LIMIT]
    latest_block_hash: Hash32
    payload_expected_withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
    # [New in eip8148]
    validator_sweep_thresholds: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
```

#### `ExecutionRequests`

```python
class ExecutionRequests(Container):
    deposits: List[DepositRequest, MAX_DEPOSIT_REQUESTS_PER_PAYLOAD]
    withdrawals: List[WithdrawalRequest, MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD]
    consolidations: List[ConsolidationRequest, MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD]
    # [New in eip8148]
    sweep_thresholds: List[SetSweepThresholdRequest, MAX_SET_SWEEP_THRESHOLD_REQUESTS_PER_PAYLOAD]
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
def is_partially_withdrawable_validator(validator: Validator, balance: Gwei, sweep_threshold: Gwei) -> bool:
    """
    Check if ``validator`` is partially withdrawable.
    """
    # [Modified in eip8148]
    effective_sweep_threshold = get_effective_sweep_threshold(validator, sweep_threshold)
    # [Modified in eip8148]
    has_effective_sweep_threshold = validator.effective_balance >= effective_sweep_threshold
    # [Modified in eip8148]
    has_excess_balance = balance > effective_sweep_threshold
    return (
        has_execution_withdrawal_credential(validator)
        # [Modified in eip8148]
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

*Note*: The function `add_validator_to_registry` is modified to initialize the item in the `validator_sweep_thresholds` list.

```python
def add_validator_to_registry(
    state: BeaconState, pubkey: BLSPubkey, withdrawal_credentials: Bytes32, amount: uint64
) -> None:
    index = get_index_for_new_validator(state)
    validator = get_validator_from_deposit(pubkey, withdrawal_credentials, amount)
    set_or_append_list(state.validators, index, validator)
    set_or_append_list(state.balances, index, amount)
    # [New in eip8148]
    set_or_append_list(state.validator_sweep_thresholds, index, Gwei(0))
    set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.inactivity_scores, index, uint64(0))
```

## Beacon chain state transition function

### Block processing

#### Execution payload

##### Modified `get_execution_requests_list`

*Note*: Encodes execution requests as defined by
[EIP-7685](https://eips.ethereum.org/EIPS/eip-7685).

```python
def get_execution_requests_list(execution_requests: ExecutionRequests) -> Sequence[bytes]:
    requests = [
        (DEPOSIT_REQUEST_TYPE, execution_requests.deposits),
        (WITHDRAWAL_REQUEST_TYPE, execution_requests.withdrawals),
        (CONSOLIDATION_REQUEST_TYPE, execution_requests.consolidations),
        # [New in eip8148]
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

*Note*: The function `get_validators_sweep_withdrawals` is modified to support eip8148.

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
        # [New in eip8148]
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
        # [Modified in eip8148]
        elif is_partially_withdrawable_validator(validator, balance, sweep_threshold):
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    # [Modified in eip8148]
                    amount=balance - get_effective_sweep_threshold(validator, sweep_threshold),
                )
            )
            withdrawal_index += WithdrawalIndex(1)

        validator_index = ValidatorIndex((validator_index + 1) % len(state.validators))
        processed_count += 1

    return withdrawals, withdrawal_index, processed_count
```

#### Operations

###### New `process_set_sweep_threshold_request`

```python
def process_set_sweep_threshold_request(state: BeaconState, set_sweep_threshold_request: SetSweepThresholdRequest) -> None:
    threshold = set_sweep_threshold_request.threshold

    validator_pubkeys = [v.pubkey for v in state.validators]
    # Verify pubkey exists
    request_pubkey = set_sweep_threshold_request.validator_pubkey
    if request_pubkey not in validator_pubkeys:
        return
    index = ValidatorIndex(validator_pubkeys.index(request_pubkey))
    validator = state.validators[index]

    # Verify withdrawal credentials
    # Only allow setting sweep threshold with compounding withdrawal credentials
    has_correct_credential = has_compounding_withdrawal_credential(validator)
    # Ensure that the source address matches the withdrawal credentials
    is_correct_source_address = (
        validator.withdrawal_credentials[12:] == set_sweep_threshold_request.source_address
    )
    if not (has_correct_credential and is_correct_source_address):
        return

    # Verify exit has not been initiated
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return

    if threshold == 0 or threshold == MAX_EFFECTIVE_BALANCE_ELECTRA:
        # Remove custom sweep threshold
        state.validator_sweep_thresholds[index] = 0
        return

    # Prevent validators from gaming the sweep cycle by setting thresholds below current balance.
    # This ensures validators cannot bypass the partial withdrawal queue to perform immediate withdrawals.
    # To lower a threshold, validators must first request a partial withdrawal, wait for processing,
    # then set the desired threshold.
    if threshold < state.balances[index]:
        return

    # Ensure threshold is a multiple of the EFFECTIVE_BALANCE_INCREMENT
    if threshold % EFFECTIVE_BALANCE_INCREMENT != 0:
        return
    
    if MIN_SWEEP_THRESHOLD <= threshold < MAX_EFFECTIVE_BALANCE_ELECTRA:
        # Set custom sweep threshold
        state.validator_sweep_thresholds[index] = threshold
```

### Execution payload processing

#### Modified `process_execution_payload`

*Note*: `process_execution_payload` now includes processing of
`SetSweepThresholdRequest` operations.

```python
def process_execution_payload(
    state: BeaconState,
    # [Modified in Gloas:EIP7732]
    # Removed `body`
    # [New in Gloas:EIP7732]
    signed_envelope: SignedExecutionPayloadEnvelope,
    execution_engine: ExecutionEngine,
    # [New in Gloas:EIP7732]
    verify: bool = True,
) -> None:
    envelope = signed_envelope.message
    payload = envelope.payload

    # Verify signature
    if verify:
        assert verify_execution_payload_envelope_signature(state, signed_envelope)

    # Cache latest block header state root
    previous_state_root = hash_tree_root(state)
    if state.latest_block_header.state_root == Root():
        state.latest_block_header.state_root = previous_state_root

    # Verify consistency with the beacon block
    assert envelope.beacon_block_root == hash_tree_root(state.latest_block_header)
    assert envelope.slot == state.slot

    # Verify consistency with the committed bid
    committed_bid = state.latest_execution_payload_bid
    assert envelope.builder_index == committed_bid.builder_index
    assert committed_bid.blob_kzg_commitments_root == hash_tree_root(envelope.blob_kzg_commitments)
    assert committed_bid.prev_randao == payload.prev_randao

    # Verify consistency with expected withdrawals
    assert hash_tree_root(payload.withdrawals) == hash_tree_root(state.payload_expected_withdrawals)

    # Verify the gas_limit
    assert committed_bid.gas_limit == payload.gas_limit
    # Verify the block hash
    assert committed_bid.block_hash == payload.block_hash
    # Verify consistency of the parent hash with respect to the previous execution payload
    assert payload.parent_hash == state.latest_block_hash
    # Verify timestamp
    assert payload.timestamp == compute_time_at_slot(state, state.slot)
    # Verify commitments are under limit
    assert (
        len(envelope.blob_kzg_commitments)
        <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
    )
    # Verify the execution payload is valid
    versioned_hashes = [
        kzg_commitment_to_versioned_hash(commitment) for commitment in envelope.blob_kzg_commitments
    ]
    requests = envelope.execution_requests
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
            execution_requests=requests,
        )
    )

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(requests.deposits, process_deposit_request)
    for_ops(requests.withdrawals, process_withdrawal_request)
    for_ops(requests.consolidations, process_consolidation_request)
    # [New in eip8148]
    for_ops(requests.sweep_thresholds, process_set_sweep_threshold_request)

    # Queue the builder payment
    payment = state.builder_pending_payments[SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH]
    amount = payment.withdrawal.amount
    if amount > 0:
        state.builder_pending_withdrawals.append(payment.withdrawal)
    state.builder_pending_payments[SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH] = (
        BuilderPendingPayment()
    )

    # Cache the execution payload hash
    state.execution_payload_availability[state.slot % SLOTS_PER_HISTORICAL_ROOT] = 0b1
    state.latest_block_hash = payload.block_hash

    # Verify the state root
    if verify:
        assert envelope.state_root == hash_tree_root(state)
```

## Testing

TBD
