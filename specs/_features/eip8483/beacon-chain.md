# EIP-8483 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `ValidatorPQRegistrationRequests`](#new-validatorpqregistrationrequests)
  - [New `ValidatorPQRegistrations`](#new-validatorpqregistrations)
  - [New `BuilderPQRegistrationRequests`](#new-builderpqregistrationrequests)
  - [New `BuilderPQRegistrations`](#new-builderpqregistrations)
- [Constants](#constants)
  - [New execution layer triggered request types](#new-execution-layer-triggered-request-types)
- [Presets](#presets)
  - [Execution](#execution)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`BeaconState`](#beaconstate)
    - [`ExecutionRequests`](#executionrequests)
  - [New containers](#new-containers)
    - [`ValidatorPQRegistrationRequest`](#validatorpqregistrationrequest)
    - [`ValidatorPQRegistration`](#validatorpqregistration)
    - [`BuilderPQRegistrationRequest`](#builderpqregistrationrequest)
    - [`BuilderPQRegistration`](#builderpqregistration)
- [Helpers](#helpers)
  - [Beacon state mutators](#beacon-state-mutators)
    - [New `remove_validator_pq_registration`](#new-remove_validator_pq_registration)
    - [New `remove_builder_pq_registration`](#new-remove_builder_pq_registration)
    - [Modified `initiate_validator_exit`](#modified-initiate_validator_exit)
    - [Modified `initiate_validator_consolidation`](#modified-initiate_validator_consolidation)
    - [Modified `initiate_builder_exit`](#modified-initiate_builder_exit)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Modified `get_execution_requests_list`](#modified-get_execution_requests_list)
    - [Operations](#operations)
      - [New `process_validator_pq_registration_request`](#new-process_validator_pq_registration_request)
      - [New `process_builder_pq_registration_request`](#new-process_builder_pq_registration_request)
    - [Parent execution payload](#parent-execution-payload)
      - [Modified `apply_parent_execution_payload`](#modified-apply_parent_execution_payload)
      - [Modified `process_parent_execution_payload`](#modified-process_parent_execution_payload)

<!-- mdformat-toc end -->

## Introduction

This upgrade adds two execution layer triggered requests, as described by
EIP-8483, with which validators and builders register opaque post-quantum (PQ)
material. A validator registers 64 bytes, enough for a new public key and a
RANDAO commitment. A builder registers only 32 bytes, enough for a new public
key, since builders do not contribute to RANDAO. This specification gives the
material no meaning beyond requiring its first 32 bytes to be unique. A later
fork that migrates to post-quantum signatures will define how it is used.

The first 32 bytes of the PQ data are intended for a PQ public key. Before
accepting a request, the predeploy contract checks a proof of possession over
them. Because these bytes must be unique, this prevents someone from
front-running a request by registering the same public key first, which would
prevent that request from being accepted.

The beacon state stores one `(validator_index, pq_data)` entry per validator and
one `(builder_pubkey, pq_data)` entry per builder. Builder entries are keyed by
public key rather than index, because a builder index is reused once its builder
has withdrawn. A later request for the same validator or builder overwrites the
earlier one. An entry is removed when its validator or builder initiates an
exit, after which that validator or builder cannot register again. These state
fields are temporary and will be removed after the migration to post-quantum
signatures.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md).

## Types

### New `ValidatorPQRegistrationRequests`

```python
class ValidatorPQRegistrationRequests(ProgressiveList[ValidatorPQRegistrationRequest]):
    """
    The validator PQ registration requests pertaining to a single execution payload.
    """
```

### New `ValidatorPQRegistrations`

```python
class ValidatorPQRegistrations(ProgressiveList[ValidatorPQRegistration]):
    """
    The registered validator PQ material, at most one entry per validator.
    """
```

### New `BuilderPQRegistrationRequests`

```python
class BuilderPQRegistrationRequests(ProgressiveList[BuilderPQRegistrationRequest]):
    """
    The builder PQ registration requests pertaining to a single execution payload.
    """
```

### New `BuilderPQRegistrations`

```python
class BuilderPQRegistrations(ProgressiveList[BuilderPQRegistration]):
    """
    The registered builder PQ material, at most one entry per builder.
    """
```

## Constants

### New execution layer triggered request types

| Name                                     | Value            |
| ---------------------------------------- | ---------------- |
| `VALIDATOR_PQ_REGISTRATION_REQUEST_TYPE` | `Bytes1("0x05")` |
| `BUILDER_PQ_REGISTRATION_REQUEST_TYPE`   | `Bytes1("0x06")` |

## Presets

### Execution

| Name                                                 | Value                     |
| ---------------------------------------------------- | ------------------------- |
| `MAX_VALIDATOR_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD` | `Uint64(2**10)` (= 1,024) |
| `MAX_BUILDER_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD`   | `Uint64(2**4)` (= 16)     |

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
    validator_pq_registrations: ValidatorPQRegistrations
    # [New in EIP8483]
    builder_pq_registrations: BuilderPQRegistrations
```

#### `ExecutionRequests`

```python
class ExecutionRequests(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=7)

    deposits: DepositRequests
    withdrawals: WithdrawalRequests
    consolidations: ConsolidationRequests
    builder_deposits: BuilderDepositRequests
    builder_exits: BuilderExitRequests
    # [New in EIP8483]
    validator_pq_registrations: ValidatorPQRegistrationRequests
    # [New in EIP8483]
    builder_pq_registrations: BuilderPQRegistrationRequests
```

### New containers

#### `ValidatorPQRegistrationRequest`

*Note*: The SSZ serialization of `ValidatorPQRegistrationRequest` is the
132-byte record returned by the validator predeploy contract.

```python
class ValidatorPQRegistrationRequest(Container):
    source_address: ExecutionAddress
    validator_pubkey: BLSPubkey
    pq_data: Bytes64
```

#### `ValidatorPQRegistration`

```python
class ValidatorPQRegistration(Container):
    validator_index: ValidatorIndex
    pq_data: Bytes64
```

#### `BuilderPQRegistrationRequest`

*Note*: The SSZ serialization of `BuilderPQRegistrationRequest` is the 100-byte
record returned by the builder predeploy contract.

```python
class BuilderPQRegistrationRequest(Container):
    source_address: ExecutionAddress
    builder_pubkey: BLSPubkey
    pq_data: Bytes32
```

#### `BuilderPQRegistration`

```python
class BuilderPQRegistration(Container):
    builder_pubkey: BLSPubkey
    pq_data: Bytes32
```

## Helpers

### Beacon state mutators

#### New `remove_validator_pq_registration`

```python
def remove_validator_pq_registration(state: BeaconState, validator_index: ValidatorIndex) -> None:
    state.validator_pq_registrations = ValidatorPQRegistrations(
        data=[
            registration
            for registration in state.validator_pq_registrations
            if registration.validator_index != validator_index
        ]
    )
```

#### New `remove_builder_pq_registration`

```python
def remove_builder_pq_registration(state: BeaconState, builder_pubkey: BLSPubkey) -> None:
    state.builder_pq_registrations = BuilderPQRegistrations(
        data=[
            registration
            for registration in state.builder_pq_registrations
            if registration.builder_pubkey != builder_pubkey
        ]
    )
```

#### Modified `initiate_validator_exit`

```python
def initiate_validator_exit(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Initiate the exit of the validator with index ``index``.
    """
    # Return if validator already initiated exit
    validator = state.validators[index]
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return

    # Compute exit queue epoch
    exit_queue_epoch = compute_exit_epoch_and_update_churn(state, validator.effective_balance)

    # Set validator exit epoch and withdrawable epoch
    validator.exit_epoch = exit_queue_epoch
    validator.withdrawable_epoch = validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY

    # [New in EIP8483]
    remove_validator_pq_registration(state, index)
```

#### Modified `initiate_validator_consolidation`

```python
def initiate_validator_consolidation(
    state: BeaconState, source_index: ValidatorIndex, target_index: ValidatorIndex
) -> None:
    """
    Initiate the consolidation of the validator with index ``source_index`` into
    the validator with index ``target_index``.
    """
    source_validator = state.validators[source_index]
    source_validator.exit_epoch = compute_consolidation_epoch_and_update_churn(
        state, source_validator.effective_balance
    )
    source_validator.withdrawable_epoch = (
        source_validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    state.pending_consolidations.append(
        PendingConsolidation(source_index=source_index, target_index=target_index)
    )

    # [New in EIP8483]
    remove_validator_pq_registration(state, source_index)
```

#### Modified `initiate_builder_exit`

```python
def initiate_builder_exit(state: BeaconState, builder_index: BuilderIndex) -> None:
    """
    Initiate the exit of the builder with index ``index``.
    """
    # Set builder exit epoch
    builder = state.builders[builder_index]
    builder.withdrawable_epoch = get_current_epoch(state) + MIN_BUILDER_WITHDRAWABILITY_DELAY

    # [New in EIP8483]
    remove_builder_pq_registration(state, builder.pubkey)
```

## Beacon chain state transition function

### Block processing

#### Execution payload

##### Modified `get_execution_requests_list`

```python
def get_execution_requests_list(execution_requests: ExecutionRequests) -> Sequence[bytes]:
    requests: Sequence[tuple[Bytes1, ProgressiveList]] = [
        (DEPOSIT_REQUEST_TYPE, execution_requests.deposits),
        (WITHDRAWAL_REQUEST_TYPE, execution_requests.withdrawals),
        (CONSOLIDATION_REQUEST_TYPE, execution_requests.consolidations),
        (BUILDER_DEPOSIT_REQUEST_TYPE, execution_requests.builder_deposits),
        (BUILDER_EXIT_REQUEST_TYPE, execution_requests.builder_exits),
        # [New in EIP8483]
        (VALIDATOR_PQ_REGISTRATION_REQUEST_TYPE, execution_requests.validator_pq_registrations),
        # [New in EIP8483]
        (BUILDER_PQ_REGISTRATION_REQUEST_TYPE, execution_requests.builder_pq_registrations),
    ]

    return [
        request_type + ssz_serialize(request_data)
        for request_type, request_data in requests
        if len(request_data) != 0
    ]
```

#### Operations

##### New `process_validator_pq_registration_request`

*Note*: Invalid requests are ignored. Validators with `0x00` or `0x01`
withdrawal credentials cannot register, and must switch to `0x02` credentials
before registering. Pending and active validators can register PQ material, as
long as the request comes from their withdrawal address and the first 32 bytes
of its PQ data are not already registered. Exited validators cannot register.

```python
def process_validator_pq_registration_request(
    state: BeaconState, request: ValidatorPQRegistrationRequest
) -> None:
    validator_pubkeys = [validator.pubkey for validator in state.validators]
    if request.validator_pubkey not in validator_pubkeys:
        return
    validator_index = ValidatorIndex(validator_pubkeys.index(request.validator_pubkey))
    validator = state.validators[validator_index]

    # Verify the validator has not initiated an exit
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return

    # Verify the validator has compounding withdrawal credentials
    if not has_compounding_withdrawal_credential(validator):
        return

    # Verify the request comes from the validator's withdrawal address
    if validator.withdrawal_credentials[12:] != request.source_address:
        return

    # Verify the first 32 bytes of the PQ data are not already registered
    for registration in state.validator_pq_registrations:
        if registration.pq_data[:32] == request.pq_data[:32]:
            return

    # Overwrite an existing registration for this validator
    for registration in state.validator_pq_registrations:
        if registration.validator_index == validator_index:
            registration.pq_data = request.pq_data
            return

    state.validator_pq_registrations.append(
        ValidatorPQRegistration(
            validator_index=validator_index,
            pq_data=request.pq_data,
        )
    )
```

##### New `process_builder_pq_registration_request`

*Note*: Invalid requests are ignored. Pending and active builders can register
PQ material, as long as the request comes from their execution address and its
PQ data is not already registered. Exited builders cannot register.

```python
def process_builder_pq_registration_request(
    state: BeaconState, request: BuilderPQRegistrationRequest
) -> None:
    builder_pubkeys = [builder.pubkey for builder in state.builders]
    if request.builder_pubkey not in builder_pubkeys:
        return
    builder_index = BuilderIndex(builder_pubkeys.index(request.builder_pubkey))
    builder = state.builders[builder_index]

    # Verify the builder has not initiated an exit
    if builder.withdrawable_epoch != FAR_FUTURE_EPOCH:
        return

    # Verify the request comes from the builder's execution address
    if builder.execution_address != request.source_address:
        return

    # Verify the PQ data is not already registered
    for registration in state.builder_pq_registrations:
        if registration.pq_data == request.pq_data:
            return

    # Overwrite an existing registration for this builder
    for registration in state.builder_pq_registrations:
        if registration.builder_pubkey == request.builder_pubkey:
            registration.pq_data = request.pq_data
            return

    state.builder_pq_registrations.append(
        BuilderPQRegistration(
            builder_pubkey=request.builder_pubkey,
            pq_data=request.pq_data,
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
    assert (
        len(requests.validator_pq_registrations)
        <= MAX_VALIDATOR_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD
    )
    # [New in EIP8483]
    assert (
        len(requests.builder_pq_registrations) <= MAX_BUILDER_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD
    )

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
    for_ops(requests.validator_pq_registrations, process_validator_pq_registration_request)
    # [New in EIP8483]
    for_ops(requests.builder_pq_registrations, process_builder_pq_registration_request)

    # Update parent payload availability and latest block hash
    state.execution_payload_availability[parent_slot % SLOTS_PER_HISTORICAL_ROOT] = Boolean(True)
    state.latest_block_hash = parent_bid.block_hash
```

##### Modified `process_parent_execution_payload`

*Note*: The first block after the fork may build on a full parent from before
the fork, whose bid commits to the Gloas `ExecutionRequests` type. Its execution
requests are verified against that type and cannot include PQ registration
requests.

```python
def process_parent_execution_payload(state: BeaconState, block: BeaconBlock) -> None:
    bid = block.body.signed_execution_payload_bid.message
    parent_bid = state.latest_execution_payload_bid
    requests = block.body.parent_execution_requests

    if bid.parent_block_hash != parent_bid.block_hash:
        # Parent was EMPTY -- no execution requests expected
        assert requests == ExecutionRequests.empty()
        return

    # [New in EIP8483]
    if compute_epoch_at_slot(parent_bid.slot) < EIP8483_FORK_EPOCH:
        # Parent was FULL before the fork -- its bid commits to the Gloas type
        assert len(requests.validator_pq_registrations) == 0
        assert len(requests.builder_pq_registrations) == 0
        requests_root = hash_tree_root(
            gloas.ExecutionRequests(
                deposits=requests.deposits,
                withdrawals=requests.withdrawals,
                consolidations=requests.consolidations,
                builder_deposits=requests.builder_deposits,
                builder_exits=requests.builder_exits,
            )
        )
    else:
        requests_root = hash_tree_root(requests)

    # [Modified in EIP8483]
    # Parent was FULL -- verify the bid commitment and apply the payload
    assert requests_root == parent_bid.execution_requests_root
    apply_parent_execution_payload(state, requests)
```
