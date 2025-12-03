# EIPXXXX -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
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
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Withdrawals](#withdrawals)
      - [Modified `get_expected_withdrawals`](#modified-get_expected_withdrawals)
    - [Operations](#operations)
      - [New `process_set_sweep_threshold_request`](#new-process_set_sweep_threshold_request)
  - [Execution payload processing](#execution-payload-processing)
    - [Modified `process_execution_payload`](#modified-process_execution_payload)
- [Testing](#testing)

<!-- mdformat-toc end -->

## Introduction

This upgrade adds transaction execution to the beacon chain as part of the
eipXXXX upgrade.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md).

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
    execution_payload_availability: Bitvector[SLOTS_PER_HISTORICAL_ROOT]
    builder_pending_payments: Vector[BuilderPendingPayment, 2 * SLOTS_PER_EPOCH]
    builder_pending_withdrawals: List[BuilderPendingWithdrawal, BUILDER_PENDING_WITHDRAWALS_LIMIT]
    latest_block_hash: Hash32
    latest_withdrawals_root: Root
    # [New in EIPXXXX]
    validator_sweep_thresholds: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
```

#### `ExecutionRequests`

```python
class ExecutionRequests(Container):
    deposits: List[DepositRequest, MAX_DEPOSIT_REQUESTS_PER_PAYLOAD]
    withdrawals: List[WithdrawalRequest, MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD]
    consolidations: List[ConsolidationRequest, MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD]
    # [New in EIPXXXX]
    set_sweep_threshold_requests: List[SetSweepThresholdRequest, MAX_SET_SWEEP_THRESHOLD_REQUESTS_PER_PAYLOAD]
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
    # [Modified in EIPXXXX]
    effective_sweep_threshold = get_effective_sweep_threshold(validator, sweep_threshold)
    # [Modified in EIPXXXX]
    has_effective_sweep_threshold = validator.effective_balance == effective_sweep_threshold
    # [Modified in EIPXXXX]
    has_excess_balance = balance > effective_sweep_threshold
    return (
        has_execution_withdrawal_credential(validator)
        # [Modified in EIPXXXX]
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

## Beacon chain state transition function

### Block processing

#### Withdrawals

##### Modified `get_expected_withdrawals`

*Note*: The function `get_expected_withdrawals` is modified to support EIPXXXX.

```python
def get_expected_withdrawals(state: BeaconState) -> Tuple[Sequence[Withdrawal], uint64, uint64]:
    epoch = get_current_epoch(state)
    withdrawal_index = state.next_withdrawal_index
    validator_index = state.next_withdrawal_validator_index
    withdrawals: List[Withdrawal] = []
    processed_partial_withdrawals_count = 0
    processed_builder_withdrawals_count = 0

    # [New in Gloas:EIP7732]
    # Sweep for builder payments
    for withdrawal in state.builder_pending_withdrawals:
        if (
            withdrawal.withdrawable_epoch > epoch
            or len(withdrawals) + 1 == MAX_WITHDRAWALS_PER_PAYLOAD
        ):
            break
        if is_builder_payment_withdrawable(state, withdrawal):
            total_withdrawn = sum(
                w.amount for w in withdrawals if w.validator_index == withdrawal.builder_index
            )
            balance = state.balances[withdrawal.builder_index] - total_withdrawn
            builder = state.validators[withdrawal.builder_index]
            if builder.slashed:
                withdrawable_balance = min(balance, withdrawal.amount)
            elif balance > MIN_ACTIVATION_BALANCE:
                withdrawable_balance = min(balance - MIN_ACTIVATION_BALANCE, withdrawal.amount)
            else:
                withdrawable_balance = 0

            if withdrawable_balance > 0:
                withdrawals.append(
                    Withdrawal(
                        index=withdrawal_index,
                        validator_index=withdrawal.builder_index,
                        address=withdrawal.fee_recipient,
                        amount=withdrawable_balance,
                    )
                )
                withdrawal_index += WithdrawalIndex(1)
        processed_builder_withdrawals_count += 1

    # Sweep for pending partial withdrawals
    bound = min(
        len(withdrawals) + MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP,
        MAX_WITHDRAWALS_PER_PAYLOAD - 1,
    )
    for withdrawal in state.pending_partial_withdrawals:
        if withdrawal.withdrawable_epoch > epoch or len(withdrawals) == bound:
            break

        validator = state.validators[withdrawal.validator_index]
        has_sufficient_effective_balance = validator.effective_balance >= MIN_ACTIVATION_BALANCE
        total_withdrawn = sum(
            w.amount for w in withdrawals if w.validator_index == withdrawal.validator_index
        )
        balance = state.balances[withdrawal.validator_index] - total_withdrawn
        has_excess_balance = balance > MIN_ACTIVATION_BALANCE
        if (
            validator.exit_epoch == FAR_FUTURE_EPOCH
            and has_sufficient_effective_balance
            and has_excess_balance
        ):
            withdrawable_balance = min(balance - MIN_ACTIVATION_BALANCE, withdrawal.amount)
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=withdrawal.validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    amount=withdrawable_balance,
                )
            )
            withdrawal_index += WithdrawalIndex(1)

        processed_partial_withdrawals_count += 1

    # Sweep for remaining.
    bound = min(len(state.validators), MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
    for _ in range(bound):
        validator = state.validators[validator_index]
        total_withdrawn = sum(w.amount for w in withdrawals if w.validator_index == validator_index)
        balance = state.balances[validator_index] - total_withdrawn
        # [New in EIPXXXX]
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
        # [Modified in EIPXXXX]
        elif is_partially_withdrawable_validator(validator, balance, sweep_threshold):
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    # [Modified in EIPXXXX]
                    amount=balance - get_effective_sweep_threshold(validator, sweep_threshold),
                )
            )
            withdrawal_index += WithdrawalIndex(1)
        if len(withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
            break
        validator_index = ValidatorIndex((validator_index + 1) % len(state.validators))
    return (
        withdrawals,
        processed_builder_withdrawals_count,
        processed_partial_withdrawals_count,
    )
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
    has_correct_credential = has_execution_withdrawal_credential(validator)
    is_correct_source_address = (
        validator.withdrawal_credentials[12:] == set_sweep_threshold_request.source_address
    )
    if not (has_correct_credential and is_correct_source_address):
        return
    # Verify the validator is active
    if not is_active_validator(validator, get_current_epoch(state)):
        return
    # Verify exit has not been initiated
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return

    # Only allow setting sweep threshold with compounding withdrawal credentials
    if not has_compounding_withdrawal_credential(validator):
        return

    if threshold == 0 or threshold == MAX_EFFECTIVE_BALANCE_ELECTRA:
        # Remove custom sweep threshold
        state.validator_sweep_thresholds[index] = 0
        return

    # Ensure threshold is not lower than balance
    if threshold < state.balances[index]:
        return

    # Ensure threshold is a multiple of the quotient
    if threshold % SWEEP_THRESHOLD_QUOTIENT != 0:
        return
    
    if MIN_ACTIVATION_BALANCE <= threshold < MAX_EFFECTIVE_BALANCE_ELECTRA:
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

    # Verify the withdrawals root
    assert hash_tree_root(payload.withdrawals) == state.latest_withdrawals_root

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
    # [New in EIPXXXX]
    for_ops(requests.set_sweep_threshold_requests, process_set_sweep_threshold_request)

    # Queue the builder payment
    payment = state.builder_pending_payments[SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH]
    amount = payment.withdrawal.amount
    if amount > 0:
        exit_queue_epoch = compute_exit_epoch_and_update_churn(state, amount)
        payment.withdrawal.withdrawable_epoch = Epoch(
            exit_queue_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
        )
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
