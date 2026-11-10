# EIP-8483 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `BuilderPQRegistrationRequests`](#new-builderpqregistrationrequests)
  - [New `BuilderPQRegistrations`](#new-builderpqregistrations)
  - [New `ValidatorPQRegistrationRequests`](#new-validatorpqregistrationrequests)
  - [New `ValidatorPQRegistrations`](#new-validatorpqregistrations)
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
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Modified `get_execution_requests_list`](#modified-get_execution_requests_list)
    - [Operations](#operations)
      - [New `process_validator_pq_registration_request`](#new-process_validator_pq_registration_request)
      - [New `process_builder_pq_registration_request`](#new-process_builder_pq_registration_request)
    - [Parent execution payload](#parent-execution-payload)
      - [Modified `apply_parent_execution_payload`](#modified-apply_parent_execution_payload)

<!-- mdformat-toc end -->

## Introduction

This upgrade adds two execution layer triggered requests with which validators
and builders register post-quantum material, as described by EIP-8483. The
withdrawal address of a validator registers 64 bytes for it, an XMSS public key
followed by a VRF root. The execution address of a builder registers 32 bytes
for it, an XMSS public key.

The beacon state stores one `(validator_index, pq_data)` entry per validator and
one `(builder_pubkey, pq_data)` entry per builder. Builder entries are keyed by
public key rather than index, because a builder index is reused once its builder
has withdrawn. A later request for the same validator or builder overwrites the
earlier one. A later fork that migrates consensus to post-quantum signatures
defines how the material is used.

*Note*: Unlike EIP-8483 as drafted, a validator request is ignored if its XMSS
public key or VRF root is already registered by a validator, and a builder
request if its XMSS public key is already registered by a builder. The material
is public, so otherwise anyone could register a copy of someone else's key or
VRF root, and the migration fork could not give each its own. A validator and a
builder may share an XMSS public key, since they sign at different leaves.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md).

## Types

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

*Note*: Invalid requests are ignored. No status is checked, so pending, active,
exited, and slashed validators can all register PQ material, as long as the
request comes from their withdrawal address and its XMSS public key and VRF root
are not already registered. A validator that registers again must change both
its XMSS public key and its VRF root, because each is checked against every
registration, including its own.

```python
def process_validator_pq_registration_request(
    state: BeaconState, request: ValidatorPQRegistrationRequest
) -> None:
    # Verify the validator exists
    validator_pubkeys = [validator.pubkey for validator in state.validators]
    if request.validator_pubkey not in validator_pubkeys:
        return
    validator_index = ValidatorIndex(validator_pubkeys.index(request.validator_pubkey))
    validator = state.validators[validator_index]

    # Verify the request comes from the validator's withdrawal address
    if validator.withdrawal_credentials[12:] != request.source_address:
        return

    # Verify the XMSS public key is not already registered
    registered_xmss_pubkeys = [
        registration.pq_data[:32] for registration in state.validator_pq_registrations
    ]
    if request.pq_data[:32] in registered_xmss_pubkeys:
        return

    # Verify the VRF root is not already registered
    registered_vrf_roots = [
        registration.pq_data[32:] for registration in state.validator_pq_registrations
    ]
    if request.pq_data[32:] in registered_vrf_roots:
        return

    # Overwrite an existing registration for this validator
    for registration in state.validator_pq_registrations:
        if registration.validator_index == validator_index:
            registration.pq_data = request.pq_data
            return

    # Otherwise append a new registration
    state.validator_pq_registrations.append(
        ValidatorPQRegistration(validator_index=validator_index, pq_data=request.pq_data)
    )
```

##### New `process_builder_pq_registration_request`

*Note*: Invalid requests are ignored. No status is checked, so active and exited
builders can both register PQ material, as long as the request comes from their
execution address and its XMSS public key is not already registered.

```python
def process_builder_pq_registration_request(
    state: BeaconState, request: BuilderPQRegistrationRequest
) -> None:
    # Verify the builder exists
    builder_pubkeys = [builder.pubkey for builder in state.builders]
    if request.builder_pubkey not in builder_pubkeys:
        return
    builder = state.builders[builder_pubkeys.index(request.builder_pubkey)]

    # Verify the request comes from the builder's execution address
    if builder.execution_address != request.source_address:
        return

    # Verify the XMSS public key is not already registered
    registered_xmss_pubkeys = [
        registration.pq_data for registration in state.builder_pq_registrations
    ]
    if request.pq_data in registered_xmss_pubkeys:
        return

    # Overwrite an existing registration for this builder
    for registration in state.builder_pq_registrations:
        if registration.builder_pubkey == request.builder_pubkey:
            registration.pq_data = request.pq_data
            return

    # Otherwise append a new registration
    state.builder_pq_registrations.append(
        BuilderPQRegistration(builder_pubkey=request.builder_pubkey, pq_data=request.pq_data)
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
