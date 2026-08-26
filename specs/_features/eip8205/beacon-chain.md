# EIP-8205 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [New `PreregistrationRequests`](#new-preregistrationrequests)
  - [New `ValidatorPreregistrations`](#new-validatorpreregistrations)
- [Constants](#constants)
  - [Domains](#domains)
  - [Execution-layer triggered requests](#execution-layer-triggered-requests)
- [Presets](#presets)
  - [Execution](#execution)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [`BeaconState`](#beaconstate)
    - [`ExecutionRequests`](#executionrequests)
  - [New containers](#new-containers)
    - [`ValidatorPreregistration`](#validatorpreregistration)
    - [`PreregistrationRequest`](#preregistrationrequest)
    - [`StoredPreregistration`](#storedpreregistration)
- [Helper functions](#helper-functions)
  - [Predicates](#predicates)
    - [New `is_valid_preregistration_signature`](#new-is_valid_preregistration_signature)
    - [New `is_active_preregistration`](#new-is_active_preregistration)
  - [Misc](#misc)
    - [New `get_stored_preregistration_index`](#new-get_stored_preregistration_index)
    - [New `get_active_preregistration`](#new-get_active_preregistration)
    - [New `remove_stored_preregistration`](#new-remove_stored_preregistration)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [New `process_preregistration_expiry`](#new-process_preregistration_expiry)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Modified `get_execution_requests_list`](#modified-get_execution_requests_list)
    - [Operations](#operations)
      - [New `process_preregistration_request`](#new-process_preregistration_request)
      - [Modified `process_deposit_request`](#modified-process_deposit_request)
    - [Parent execution payload](#parent-execution-payload)
      - [Modified `apply_parent_execution_payload`](#modified-apply_parent_execution_payload)

<!-- mdformat-toc end -->

## Introduction

This upgrade adds withdrawal credentials preregistration to the beacon chain as
part of the EIP-8205 upgrade. A preregistration binds a validator pubkey to
withdrawal credentials before the validator's first deposit is processed,
protecting delegated staking deployments against deposit front-running.

This document specifies the beacon chain changes required to support these
preregistrations. The upgrade introduces a new request type within the execution
payload, triggered by execution layer transactions, which stores a
pubkey-to-withdrawal-credentials binding in the beacon state. While a binding is
active, a deposit request for the bound pubkey is discarded unless its
withdrawal credentials match the binding and its signature is valid.

*Note*: This specification is built upon [Heze](../../heze/beacon-chain.md).

## Types

### New `PreregistrationRequests`

```python
class PreregistrationRequests(ProgressiveList[PreregistrationRequest]):
    """
    The preregistration requests pertaining to a single execution payload.
    """
```

### New `ValidatorPreregistrations`

```python
class ValidatorPreregistrations(ProgressiveList[StoredPreregistration]):
    """
    The preregistrations stored in the beacon state, including expired
    records not yet garbage-collected.
    """
```

## Constants

### Domains

*Note*: Preregistration signatures use a fork-agnostic domain computed with
`compute_domain`, so a preregistration signed once remains valid across fork
boundaries, like a deposit signature. Unlike deposit signatures, the domain is
bound to the chain through `genesis_validators_root`, which prevents
cross-network replay.

| Name                     | Value                      |
| ------------------------ | -------------------------- |
| `DOMAIN_PREREGISTRATION` | `DomainType('0x11000000')` |

### Execution-layer triggered requests

| Name                           | Value            |
| ------------------------------ | ---------------- |
| `PREREGISTRATION_REQUEST_TYPE` | `Bytes1('0x05')` |

## Presets

### Execution

| Name                                       | Value                       |
| ------------------------------------------ | --------------------------- |
| `MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD` | `Uint64(2**2)` (= 4)        |
| `PREREGISTRATIONS_LIMIT`                   | `Uint64(2**19)` (= 524,288) |
| `PREREGISTRATION_EXPIRY_SLOTS`             | `Slot(2**18)` (= 262,144)   |

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
    ptc_window: PayloadTimelinessCommitteeWindow
    # [New in EIP8205]
    validator_preregistrations: ValidatorPreregistrations
```

#### `ExecutionRequests`

```python
class ExecutionRequests(ProgressiveContainer(active_fields=[1] * 6)):
    deposits: DepositRequests
    withdrawals: WithdrawalRequests
    consolidations: ConsolidationRequests
    builder_deposits: BuilderDepositRequests
    builder_exits: BuilderExitRequests
    # [New in EIP8205]
    preregistrations: PreregistrationRequests
```

### New containers

#### `ValidatorPreregistration`

*Note*: This is the signing container for preregistration signatures.

```python
class ValidatorPreregistration(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
```

#### `PreregistrationRequest`

```python
class PreregistrationRequest(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
    signature: BLSSignature
```

#### `StoredPreregistration`

*Note*: `expiry_slot` is the absolute deadline computed when the preregistration
is stored. A later change to `PREREGISTRATION_EXPIRY_SLOTS` therefore affects
only newly stored records.

```python
class StoredPreregistration(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
    expiry_slot: Slot
```

## Helper functions

### Predicates

#### New `is_valid_preregistration_signature`

```python
def is_valid_preregistration_signature(state: BeaconState, request: PreregistrationRequest) -> bool:
    preregistration = ValidatorPreregistration(
        pubkey=request.pubkey,
        withdrawal_credentials=request.withdrawal_credentials,
    )
    domain = compute_domain(
        DOMAIN_PREREGISTRATION,
        genesis_validators_root=state.genesis_validators_root,
    )
    signing_root = compute_signing_root(preregistration, domain)
    return bls.Verify(request.pubkey, signing_root, request.signature)
```

#### New `is_active_preregistration`

*Note*: Activity is evaluated against the slot of the outstanding parent
payload, whose execution requests are the ones being applied during block
processing. Once stored, a binding therefore remains active for subsequently
processed payloads whose slots are below its stored `expiry_slot`, regardless of
when the expired record is physically swept.

```python
def is_active_preregistration(state: BeaconState, preregistration: StoredPreregistration) -> bool:
    parent_slot = state.latest_execution_payload_bid.slot
    return parent_slot < preregistration.expiry_slot
```

### Misc

*Note*: Implementations should maintain secondary pubkey indices over
`validator_preregistrations` and `pending_deposits` instead of the linear scans
shown here. Removals must preserve the remaining list order, which is
consensus-visible through the state root. Since the state root is only computed
after block processing, implementations SHOULD NOT rebuild the list once per
removed record: consumed records can be tombstoned during request processing and
the list compacted in a single pass per block, which produces an identical
post-state.

#### New `get_stored_preregistration_index`

```python
def get_stored_preregistration_index(state: BeaconState, pubkey: BLSPubkey) -> Optional[Uint64]:
    for index, preregistration in enumerate(state.validator_preregistrations):
        if preregistration.pubkey == pubkey:
            return Uint64(index)
    return None
```

#### New `get_active_preregistration`

```python
def get_active_preregistration(
    state: BeaconState, pubkey: BLSPubkey
) -> Optional[StoredPreregistration]:
    index = get_stored_preregistration_index(state, pubkey)
    if index is None:
        return None
    preregistration = state.validator_preregistrations[index]
    if not is_active_preregistration(state, preregistration):
        return None
    return preregistration
```

#### New `remove_stored_preregistration`

```python
def remove_stored_preregistration(state: BeaconState, pubkey: BLSPubkey) -> None:
    state.validator_preregistrations = ValidatorPreregistrations([
        preregistration
        for preregistration in state.validator_preregistrations
        if preregistration.pubkey != pubkey
    ])
```

## Beacon chain state transition function

### Epoch processing

#### Modified `process_epoch`

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_pending_deposits(state)
    process_pending_consolidations(state)
    process_builder_pending_payments(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
    process_proposer_lookahead(state)
    process_ptc_window(state)
    # [New in EIP8205]
    process_preregistration_expiry(state)
```

#### New `process_preregistration_expiry`

*Note*: The sweep is garbage collection only: bindings are enforced through
`is_active_preregistration`, so its timing has no effect on whether a binding is
enforced or a request is admitted, and expiry is independent of finality. An
expired record may therefore remain physically stored until the next sweep.
Reusing the same predicate, which is keyed to the outstanding parent bid,
guarantees that a record is never removed while a payload it still covers
remains outstanding.

```python
def process_preregistration_expiry(state: BeaconState) -> None:
    state.validator_preregistrations = ValidatorPreregistrations([
        preregistration
        for preregistration in state.validator_preregistrations
        if is_active_preregistration(state, preregistration)
    ])
```

### Block processing

#### Execution payload

##### Modified `get_execution_requests_list`

```python
def get_execution_requests_list(execution_requests: ExecutionRequests) -> Sequence[bytes]:
    requests: Sequence[Tuple[Bytes1, ProgressiveList]] = [
        (DEPOSIT_REQUEST_TYPE, execution_requests.deposits),
        (WITHDRAWAL_REQUEST_TYPE, execution_requests.withdrawals),
        (CONSOLIDATION_REQUEST_TYPE, execution_requests.consolidations),
        (BUILDER_DEPOSIT_REQUEST_TYPE, execution_requests.builder_deposits),
        (BUILDER_EXIT_REQUEST_TYPE, execution_requests.builder_exits),
        # [New in EIP8205]
        (PREREGISTRATION_REQUEST_TYPE, execution_requests.preregistrations),
    ]

    return [
        request_type + ssz_serialize(request_data)
        for request_type, request_data in requests
        if len(request_data) != 0
    ]
```

#### Operations

##### New `process_preregistration_request`

```python
def process_preregistration_request(state: BeaconState, request: PreregistrationRequest) -> None:
    pubkey = request.pubkey

    # An active binding for this pubkey makes the new request a no-op,
    # whether the duplicate is exact or conflicting
    if get_active_preregistration(state, pubkey) is not None:
        return

    # A pubkey with an existing validator cannot be preregistered
    if pubkey in [validator.pubkey for validator in state.validators]:
        return

    # A pubkey with a valid pending deposit cannot be preregistered
    if is_pending_validator(state.pending_deposits, pubkey):
        return

    # The capacity check counts only active records, so the timing of the
    # garbage-collection sweep does not affect admission. It applies to
    # appends and to replacements alike, since both create an active binding
    active_preregistrations = [
        preregistration
        for preregistration in state.validator_preregistrations
        if is_active_preregistration(state, preregistration)
    ]
    if len(active_preregistrations) >= PREREGISTRATIONS_LIMIT:
        return

    if not is_valid_preregistration_signature(state, request):
        return

    preregistration = StoredPreregistration(
        pubkey=pubkey,
        withdrawal_credentials=request.withdrawal_credentials,
        expiry_slot=Slot(state.slot + PREREGISTRATION_EXPIRY_SLOTS),
    )
    index = get_stored_preregistration_index(state, pubkey)
    if index is not None:
        # Replace the expired record in place
        state.validator_preregistrations[index] = preregistration
    else:
        state.validator_preregistrations.append(preregistration)
```

##### Modified `process_deposit_request`

*Note*: The function `process_deposit_request` is modified to enforce an active
preregistration binding.

```python
def process_deposit_request(state: BeaconState, deposit_request: DepositRequest) -> None:
    # [New in EIP8205]
    preregistration = get_active_preregistration(state, deposit_request.pubkey)
    if preregistration is not None:
        if deposit_request.withdrawal_credentials != preregistration.withdrawal_credentials:
            return

        if not is_valid_deposit_signature(
            deposit_request.pubkey,
            deposit_request.withdrawal_credentials,
            deposit_request.amount,
            deposit_request.signature,
        ):
            return

        remove_stored_preregistration(state, deposit_request.pubkey)

    state.pending_deposits.append(
        PendingDeposit(
            pubkey=deposit_request.pubkey,
            withdrawal_credentials=deposit_request.withdrawal_credentials,
            amount=deposit_request.amount,
            signature=deposit_request.signature,
            slot=state.slot,
        )
    )
```

#### Parent execution payload

##### Modified `apply_parent_execution_payload`

*Note*: Preregistrations are processed last so that a deposit and a
preregistration for the same pubkey in one execution payload retain the
deposit-first behavior stated by EIP-8205.

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
    # [New in EIP8205]
    assert len(requests.preregistrations) <= MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD

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
    # [New in EIP8205]
    for_ops(requests.preregistrations, process_preregistration_request)

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
