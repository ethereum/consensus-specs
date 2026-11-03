# EIP-8483 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `BuilderPQRegistrations`](#new-builderpqregistrations)
  - [New `PQRegistrationRequests`](#new-pqregistrationrequests)
  - [New `PQRegistrations`](#new-pqregistrations)
- [Constants](#constants)
  - [New execution layer triggered request type](#new-execution-layer-triggered-request-type)
- [Presets](#presets)
  - [Execution](#execution)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`BeaconState`](#beaconstate)
    - [`ExecutionRequests`](#executionrequests)
  - [New containers](#new-containers)
    - [`PQRegistrationRequest`](#pqregistrationrequest)
    - [`PQRegistration`](#pqregistration)
    - [`BuilderPQRegistration`](#builderpqregistration)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Modified `get_execution_requests_list`](#modified-get_execution_requests_list)
    - [Operations](#operations)
      - [New `process_pq_registration_request`](#new-process_pq_registration_request)
      - [New `process_builder_pq_registration_request`](#new-process_builder_pq_registration_request)
    - [Parent execution payload](#parent-execution-payload)
      - [Modified `apply_parent_execution_payload`](#modified-apply_parent_execution_payload)

<!-- mdformat-toc end -->

## Introduction

This upgrade adds an execution layer triggered request with which the execution
address in a validator's withdrawal credentials registers 32 bytes of opaque
post-quantum material for that validator, as part of the EIP-8483 upgrade.

The beacon state stores one `(validator_index, pq_data)` pair per validator. A
later request from the same owner overwrites the earlier one. This upgrade gives
the 32 bytes no meaning. A later fork that migrates consensus to post-quantum
signatures defines how they are used.

*Note*: Unlike EIP-8483 as drafted, this feature also lets a builder register,
with the builder's public key in place of the validator's and its execution
address as the authority. Builders keep their balance across a post-quantum
migration only if they can carry a key through it. Builder indices are reused,
so a builder registration is keyed by public key rather than index.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md).

## Types

### New `BuilderPQRegistrations`

```python
class BuilderPQRegistrations(ProgressiveList[BuilderPQRegistration]):
    """
    The registered PQ material of builders, at most one entry per builder
    public key.
    """
```

### New `PQRegistrationRequests`

```python
class PQRegistrationRequests(ProgressiveList[PQRegistrationRequest]):
    """
    The PQ registration requests pertaining to a single execution payload.
    """
```

### New `PQRegistrations`

```python
class PQRegistrations(ProgressiveList[PQRegistration]):
    """
    The registered PQ material, at most one entry per validator.
    """
```

## Constants

### New execution layer triggered request type

| Name                           | Value            |
| ------------------------------ | ---------------- |
| `PQ_REGISTRATION_REQUEST_TYPE` | `Bytes1("0x06")` |

## Presets

### Execution

| Name                                       | Value                 | Description                                                                               |
| ------------------------------------------ | --------------------- | ----------------------------------------------------------------------------------------- |
| `MAX_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD` | `Uint64(2**4)` (= 16) | *[New in EIP8483]* Maximum number of execution layer PQ registration requests per payload |

## Containers

### Modified containers

#### `BeaconState`

```python
class BeaconState(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=48)

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
    ptc_window: PayloadTimelinessCommitteeWindow
    # [New in EIP8483]
    pq_registrations: PQRegistrations
    # [New in EIP8483]
    builder_pq_registrations: BuilderPQRegistrations
```

#### `ExecutionRequests`

```python
class ExecutionRequests(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=6)

    deposits: DepositRequests
    withdrawals: WithdrawalRequests
    consolidations: ConsolidationRequests
    builder_deposits: BuilderDepositRequests
    builder_exits: BuilderExitRequests
    # [New in EIP8483]
    pq_registrations: PQRegistrationRequests
```

### New containers

#### `PQRegistrationRequest`

*Note*: The SSZ serialization of `PQRegistrationRequest` is the 100-byte record
returned by the predeploy contract.

```python
class PQRegistrationRequest(Container):
    source_address: ExecutionAddress
    validator_pubkey: BLSPubkey
    pq_data: Bytes32
```

#### `PQRegistration`

```python
class PQRegistration(Container):
    validator_index: ValidatorIndex
    pq_data: Bytes32
```

#### `BuilderPQRegistration`

```python
class BuilderPQRegistration(Container):
    builder_pubkey: BLSPubkey
    pq_data: Bytes32
```

## Beacon chain state transition function

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
        # [New in EIP8483]
        (PQ_REGISTRATION_REQUEST_TYPE, execution_requests.pq_registrations),
    ]

    return [
        request_type + ssz_serialize(request_data)
        for request_type, request_data in requests
        if len(request_data) != 0
    ]
```

#### Operations

##### New `process_pq_registration_request`

*Note*: Invalid requests are ignored. No validator status is checked, so
pending, active, exited, and slashed validators can all register PQ material, as
long as the request comes from their withdrawal address. A request for a public
key that is not a validator's is handled as a builder registration.

```python
def process_pq_registration_request(
    state: BeaconState, pq_registration_request: PQRegistrationRequest
) -> None:
    # Verify the validator exists
    validator_pubkeys = [validator.pubkey for validator in state.validators]
    request_pubkey = pq_registration_request.validator_pubkey
    if request_pubkey not in validator_pubkeys:
        process_builder_pq_registration_request(state, pq_registration_request)
        return
    validator_index = ValidatorIndex(validator_pubkeys.index(request_pubkey))
    validator = state.validators[validator_index]

    # Verify the request comes from the validator's withdrawal address
    has_correct_credential = has_execution_withdrawal_credential(validator)
    is_correct_source_address = (
        validator.withdrawal_credentials[12:] == pq_registration_request.source_address
    )
    if not (has_correct_credential and is_correct_source_address):
        return

    # Overwrite an existing registration for this validator
    for registration in state.pq_registrations:
        if registration.validator_index == validator_index:
            registration.pq_data = pq_registration_request.pq_data
            return

    # Otherwise append a new registration
    state.pq_registrations.append(
        PQRegistration(
            validator_index=validator_index,
            pq_data=pq_registration_request.pq_data,
        )
    )
```

##### New `process_builder_pq_registration_request`

*Note*: As for validators, no builder status is checked.

```python
def process_builder_pq_registration_request(
    state: BeaconState, pq_registration_request: PQRegistrationRequest
) -> None:
    # Verify the builder exists
    builder_pubkeys = [builder.pubkey for builder in state.builders]
    request_pubkey = pq_registration_request.validator_pubkey
    if request_pubkey not in builder_pubkeys:
        return
    builder = state.builders[BuilderIndex(builder_pubkeys.index(request_pubkey))]

    # Verify the request comes from the builder's execution address
    if builder.execution_address != pq_registration_request.source_address:
        return

    # Overwrite an existing registration for this builder
    for registration in state.builder_pq_registrations:
        if registration.builder_pubkey == request_pubkey:
            registration.pq_data = pq_registration_request.pq_data
            return

    # Otherwise append a new registration
    state.builder_pq_registrations.append(
        BuilderPQRegistration(
            builder_pubkey=request_pubkey,
            pq_data=pq_registration_request.pq_data,
        )
    )
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
    # [New in EIP8483]
    assert len(requests.pq_registrations) <= MAX_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD

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
    # [New in EIP8483]
    for_ops(requests.pq_registrations, process_pq_registration_request)

    # Update parent payload availability and latest block hash
    state.execution_payload_availability[parent_slot % SLOTS_PER_HISTORICAL_ROOT] = Boolean(True)
    state.latest_block_hash = parent_bid.block_hash
```
