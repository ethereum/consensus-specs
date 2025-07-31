# EIP-7732 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Domain types](#domain-types)
  - [Misc](#misc)
- [Preset](#preset)
  - [Misc](#misc-1)
  - [Max operations per block](#max-operations-per-block)
  - [State list lengths](#state-list-lengths)
  - [Withdrawal prefixes](#withdrawal-prefixes)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`BuilderPendingPayment`](#builderpendingpayment)
    - [`BuilderPendingWithdrawal`](#builderpendingwithdrawal)
    - [`PayloadAttestationData`](#payloadattestationdata)
    - [`PayloadAttestation`](#payloadattestation)
    - [`PayloadAttestationMessage`](#payloadattestationmessage)
    - [`IndexedPayloadAttestation`](#indexedpayloadattestation)
    - [`SignedExecutionPayloadHeader`](#signedexecutionpayloadheader)
    - [`ExecutionPayloadEnvelope`](#executionpayloadenvelope)
    - [`SignedExecutionPayloadEnvelope`](#signedexecutionpayloadenvelope)
  - [Modified containers](#modified-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
    - [`BeaconState`](#beaconstate)
- [Helper functions](#helper-functions)
  - [Math](#math)
    - [New `bit_floor`](#new-bit_floor)
  - [Misc](#misc-2)
    - [New `remove_flag`](#new-remove_flag)
  - [Predicates](#predicates)
    - [New `has_builder_withdrawal_credentials`](#new-has_builder_withdrawal_credentials)
    - [Modified `has_compounding_withdrawal_credential`](#modified-has_compounding_withdrawal_credential)
    - [New `is_attestation_same_slot`](#new-is_attestation_same_slot)
    - [New `is_builder_withdrawal_credential`](#new-is_builder_withdrawal_credential)
    - [New `is_valid_indexed_payload_attestation`](#new-is_valid_indexed_payload_attestation)
    - [New `is_parent_block_full`](#new-is_parent_block_full)
  - [Beacon State accessors](#beacon-state-accessors)
    - [New `get_attestation_participation_flag_indices`](#new-get_attestation_participation_flag_indices)
    - [New `get_ptc`](#new-get_ptc)
    - [New `get_payload_attesting_indices`](#new-get_payload_attesting_indices)
    - [New `get_indexed_payload_attestation`](#new-get_indexed_payload_attestation)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Modified `process_slot`](#modified-process_slot)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [New `process_builder_pending_payments`](#new-process_builder_pending_payments)
  - [Block processing](#block-processing)
    - [Withdrawals](#withdrawals)
      - [New `is_builder_payment_withdrawable`](#new-is_builder_payment_withdrawable)
      - [Modified `get_expected_withdrawals`](#modified-get_expected_withdrawals)
      - [Modified `process_withdrawals`](#modified-process_withdrawals)
    - [Execution payload header](#execution-payload-header)
      - [New `verify_execution_payload_header_signature`](#new-verify_execution_payload_header_signature)
      - [New `process_execution_payload_header`](#new-process_execution_payload_header)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [Attestations](#attestations)
        - [Modified `process_attestation`](#modified-process_attestation)
      - [Payload Attestations](#payload-attestations)
        - [New `process_payload_attestation`](#new-process_payload_attestation)
    - [Modified `is_merge_transition_complete`](#modified-is_merge_transition_complete)
    - [Modified `validate_merge_block`](#modified-validate_merge_block)
  - [Execution payload processing](#execution-payload-processing)
    - [New `verify_execution_payload_envelope_signature`](#new-verify_execution_payload_envelope_signature)
    - [New `process_execution_payload`](#new-process_execution_payload)

<!-- mdformat-toc end -->

## Introduction

This is the beacon chain specification of the enshrined proposer builder
separation feature.

*Note*: This specification is built upon
[Electra](../../electra/beacon-chain.md) and is under active development.

This feature adds new staked consensus participants called *Builders* and new
honest validators duties called *payload timeliness attestations*. The slot is
divided in **four** intervals. Honest validators gather *signed bids* (a
`SignedExecutionPayloadHeader`) from builders and submit their consensus blocks
(a `SignedBeaconBlock`) including accepted bids at the beginning of the slot. At
the start of the second interval, honest validators submit attestations just as
they do previous to this feature). At the start of the third interval,
aggregators aggregate these attestations and the builder broadcasts either a
full payload or a message indicating that they are withholding the payload (a
`SignedExecutionPayloadEnvelope`). At the start of the fourth interval, some
validators selected to be members of the new **Payload Timeliness Committee**
(PTC) attest to the presence and timeliness of the builder's payload.

At any given slot, the status of the blockchain's head may be either

- A block from a previous slot (e.g. the current slot's proposer did not submit
  its block).
- An *empty* block from the current slot (e.g. the proposer submitted a timely
  block, but the builder did not reveal the payload on time).
- A full block for the current slot (both the proposer and the builder revealed
  on time).

## Constants

### Domain types

| Name                    | Value                      |
| ----------------------- | -------------------------- |
| `DOMAIN_BEACON_BUILDER` | `DomainType('0x1B000000')` |
| `DOMAIN_PTC_ATTESTER`   | `DomainType('0x0C000000')` |

### Misc

| Name                                    | Value        |
| --------------------------------------- | ------------ |
| `BUILDER_PAYMENT_THRESHOLD_NUMERATOR`   | `uint64(6)`  |
| `BUILDER_PAYMENT_THRESHOLD_DENOMINATOR` | `uint64(10)` |

## Preset

### Misc

| Name       | Value                 |
| ---------- | --------------------- |
| `PTC_SIZE` | `uint64(2**9)` (=512) |

### Max operations per block

| Name                       | Value |
| -------------------------- | ----- |
| `MAX_PAYLOAD_ATTESTATIONS` | `4`   |

### State list lengths

| Name                                | Value                         | Unit                        |
| ----------------------------------- | ----------------------------- | --------------------------- |
| `BUILDER_PENDING_WITHDRAWALS_LIMIT` | `uint64(2**20)` (= 1,048,576) | Builder pending withdrawals |

### Withdrawal prefixes

| Name                        | Value            | Description                                |
| --------------------------- | ---------------- | ------------------------------------------ |
| `BUILDER_WITHDRAWAL_PREFIX` | `Bytes1('0x03')` | Withdrawal credential prefix for a builder |

## Containers

### New containers

#### `BuilderPendingPayment`

```python
class BuilderPendingPayment(Container):
    weight: Gwei
    withdrawal: BuilderPendingWithdrawal
```

#### `BuilderPendingWithdrawal`

```python
class BuilderPendingWithdrawal(Container):
    fee_recipient: ExecutionAddress
    amount: Gwei
    builder_index: ValidatorIndex
    withdrawable_epoch: Epoch
```

#### `PayloadAttestationData`

```python
class PayloadAttestationData(Container):
    beacon_block_root: Root
    slot: Slot
    payload_present: boolean
    blob_data_available: boolean
```

#### `PayloadAttestation`

```python
class PayloadAttestation(Container):
    aggregation_bits: Bitvector[PTC_SIZE]
    data: PayloadAttestationData
    signature: BLSSignature
```

#### `PayloadAttestationMessage`

```python
class PayloadAttestationMessage(Container):
    validator_index: ValidatorIndex
    data: PayloadAttestationData
    signature: BLSSignature
```

#### `IndexedPayloadAttestation`

```python
class IndexedPayloadAttestation(Container):
    attesting_indices: List[ValidatorIndex, PTC_SIZE]
    data: PayloadAttestationData
    signature: BLSSignature
```

#### `SignedExecutionPayloadHeader`

```python
class SignedExecutionPayloadHeader(Container):
    message: ExecutionPayloadHeader
    signature: BLSSignature
```

#### `ExecutionPayloadEnvelope`

```python
class ExecutionPayloadEnvelope(Container):
    payload: ExecutionPayload
    execution_requests: ExecutionRequests
    builder_index: ValidatorIndex
    beacon_block_root: Root
    slot: Slot
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    state_root: Root
```

#### `SignedExecutionPayloadEnvelope`

```python
class SignedExecutionPayloadEnvelope(Container):
    message: ExecutionPayloadEnvelope
    signature: BLSSignature
```

### Modified containers

#### `BeaconBlockBody`

*Note*: The `BeaconBlockBody` container is modified to contain a
`SignedExecutionPayloadHeader`. The containers `BeaconBlock` and
`SignedBeaconBlock` are modified indirectly. The field `execution_requests` is
removed from the beacon block body and moved into the signed execution payload
envelope.

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS_ELECTRA]
    attestations: List[Attestation, MAX_ATTESTATIONS_ELECTRA]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    # [Modified in EIP7732]
    # Removed `execution_payload`
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    # [Modified in EIP7732]
    # Removed `blob_kzg_commitments`
    # [Modified in EIP7732]
    # Removed `execution_requests`
    # [New in EIP7732]
    signed_execution_payload_header: SignedExecutionPayloadHeader
    # [New in EIP7732]
    payload_attestations: List[PayloadAttestation, MAX_PAYLOAD_ATTESTATIONS]
```

#### `ExecutionPayloadHeader`

*Note*: The `ExecutionPayloadHeader` is modified to only contain the block hash
of the committed `ExecutionPayload` in addition to the builder's payment
information, gas limit and KZG commitments root to verify the inclusion proofs.

```python
class ExecutionPayloadHeader(Container):
    parent_block_hash: Hash32
    parent_block_root: Root
    block_hash: Hash32
    fee_recipient: ExecutionAddress
    gas_limit: uint64
    builder_index: ValidatorIndex
    slot: Slot
    value: Gwei
    blob_kzg_commitments_root: Root
```

#### `BeaconState`

*Note*: The `BeaconState` is modified to track the last withdrawals honored in
the CL. The `latest_execution_payload_header` is modified semantically to refer
not to a past committed `ExecutionPayload` but instead it corresponds to the
state's slot builder's bid. Another addition is to track the last committed
block hash and the last slot that was full, that is in which there were both
consensus and execution blocks included.

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
    latest_execution_payload_header: ExecutionPayloadHeader
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
    # [New in EIP7732]
    execution_payload_availability: Bitvector[SLOTS_PER_HISTORICAL_ROOT]
    # [New in EIP7732]
    builder_pending_payments: Vector[BuilderPendingPayment, 2 * SLOTS_PER_EPOCH]
    # [New in EIP7732]
    builder_pending_withdrawals: List[BuilderPendingWithdrawal, BUILDER_PENDING_WITHDRAWALS_LIMIT]
    # [New in EIP7732]
    latest_block_hash: Hash32
    # [New in EIP7732]
    latest_full_slot: Slot
    # [New in EIP7732]
    latest_withdrawals_root: Root
```

## Helper functions

### Math

#### New `bit_floor`

```python
def bit_floor(n: uint64) -> uint64:
    """
    if ``n`` is not zero, returns the largest power of `2` that is not greater than `n`.
    """
    if n == 0:
        return 0
    return uint64(1) << (n.bit_length() - 1)
```

### Misc

#### New `remove_flag`

```python
def remove_flag(flags: ParticipationFlags, flag_index: int) -> ParticipationFlags:
    flag = ParticipationFlags(2**flag_index)
    return flags & ~flag
```

### Predicates

#### New `has_builder_withdrawal_credentials`

```python
def has_builder_withdrawal_credential(validator: Validator) -> bool:
    """
    Check if ``validator`` has an 0x03 prefixed "builder" withdrawal credential.
    """
    return is_builder_withdrawal_credential(validator.withdrawal_credentials)
```

#### Modified `has_compounding_withdrawal_credential`

*Note*: the function `has_compounding_withdrawal_credential` is modified to
return true for builders.

```python
def has_compounding_withdrawal_credential(validator: Validator) -> bool:
    """
    Check if ``validator`` has an 0x02 or 0x03 prefixed withdrawal credential.
    """
    return is_compounding_withdrawal_credential(
        validator.withdrawal_credentials
    ) or is_builder_withdrawal_credential(validator.withdrawal_credentials)
```

#### New `is_attestation_same_slot`

```python
def is_attestation_same_slot(state: BeaconState, data: AttestationData) -> bool:
    """
    Checks if the attestation was for the block proposed at the attestation slot
    """
    if data.slot == 0:
        return True
    is_matching_blockroot = data.beacon_block_root == get_block_root_at_slot(state, Slot(data.slot))
    is_current_blockroot = data.beacon_block_root != get_block_root_at_slot(
        state, Slot(data.slot - 1)
    )
    return is_matching_blockroot and is_current_blockroot
```

#### New `is_builder_withdrawal_credential`

```python
def is_builder_withdrawal_credential(withdrawal_credentials: Bytes32) -> bool:
    return withdrawal_credentials[:1] == BUILDER_WITHDRAWAL_PREFIX
```

#### New `is_valid_indexed_payload_attestation`

```python
def is_valid_indexed_payload_attestation(
    state: BeaconState, indexed_payload_attestation: IndexedPayloadAttestation
) -> bool:
    """
    Check if ``indexed_payload_attestation`` is not empty, has sorted and unique indices and has
    a valid aggregate signature.
    """
    # Verify indices are sorted and unique
    indices = indexed_payload_attestation.attesting_indices
    if len(indices) == 0 or not indices == sorted(set(indices)):
        return False

    # Verify aggregate signature
    pubkeys = [state.validators[i].pubkey for i in indices]
    domain = get_domain(state, DOMAIN_PTC_ATTESTER, None)
    signing_root = compute_signing_root(indexed_payload_attestation.data, domain)
    return bls.FastAggregateVerify(pubkeys, signing_root, indexed_payload_attestation.signature)
```

#### New `is_parent_block_full`

This function returns true if the last committed payload header was fulfilled
with a payload, this can only happen when both beacon block and payload were
present. This function must be called on a beacon state before processing the
execution payload header in the block.

```python
def is_parent_block_full(state: BeaconState) -> bool:
    return state.latest_execution_payload_header.block_hash == state.latest_block_hash
```

### Beacon State accessors

#### New `get_attestation_participation_flag_indices`

```python
def get_attestation_participation_flag_indices(
    state: BeaconState, data: AttestationData, inclusion_delay: uint64
) -> Sequence[int]:
    """
    Return the flag indices that are satisfied by an attestation.
    """
    if data.target.epoch == get_current_epoch(state):
        justified_checkpoint = state.current_justified_checkpoint
    else:
        justified_checkpoint = state.previous_justified_checkpoint

    # Matching roots
    is_matching_source = data.source == justified_checkpoint
    is_matching_target = is_matching_source and data.target.root == get_block_root(
        state, data.target.epoch
    )
    is_matching_blockroot = is_matching_target and data.beacon_block_root == get_block_root_at_slot(
        state, Slot(data.slot)
    )
    is_matching_payload = False
    if is_attestation_same_slot(state, data):
        assert data.index == 0
        is_matching_payload = True
    else:
        is_matching_payload = (
            data.index
            == state.execution_payload_availability[data.slot % SLOTS_PER_HISTORICAL_ROOT]
        )
    is_matching_head = is_matching_blockroot and is_matching_payload

    assert is_matching_source

    participation_flag_indices = []
    if is_matching_source and inclusion_delay <= integer_squareroot(SLOTS_PER_EPOCH):
        participation_flag_indices.append(TIMELY_SOURCE_FLAG_INDEX)
    if is_matching_target and inclusion_delay <= SLOTS_PER_EPOCH:
        participation_flag_indices.append(TIMELY_TARGET_FLAG_INDEX)
    if is_matching_head and inclusion_delay == MIN_ATTESTATION_INCLUSION_DELAY:
        participation_flag_indices.append(TIMELY_HEAD_FLAG_INDEX)

    return participation_flag_indices
```

#### New `get_ptc`

```python
def get_ptc(state: BeaconState, slot: Slot) -> Vector[ValidatorIndex, PTC_SIZE]:
    """
    Get the payload timeliness committee for the given ``slot``
    """
    epoch = compute_epoch_at_slot(slot)
    committees_per_slot = bit_floor(min(get_committee_count_per_slot(state, epoch), PTC_SIZE))
    members_per_committee = PTC_SIZE // committees_per_slot

    validator_indices: List[ValidatorIndex] = []
    for idx in range(committees_per_slot):
        beacon_committee = get_beacon_committee(state, slot, CommitteeIndex(idx))
        validator_indices += beacon_committee[:members_per_committee]
    return validator_indices
```

#### New `get_payload_attesting_indices`

```python
def get_payload_attesting_indices(
    state: BeaconState, slot: Slot, payload_attestation: PayloadAttestation
) -> Set[ValidatorIndex]:
    """
    Return the set of attesting indices corresponding to ``payload_attestation``.
    """
    ptc = get_ptc(state, slot)
    return set(index for i, index in enumerate(ptc) if payload_attestation.aggregation_bits[i])
```

#### New `get_indexed_payload_attestation`

```python
def get_indexed_payload_attestation(
    state: BeaconState, slot: Slot, payload_attestation: PayloadAttestation
) -> IndexedPayloadAttestation:
    """
    Return the indexed payload attestation corresponding to ``payload_attestation``.
    """
    attesting_indices = get_payload_attesting_indices(state, slot, payload_attestation)

    return IndexedPayloadAttestation(
        attesting_indices=sorted(attesting_indices),
        data=payload_attestation.data,
        signature=payload_attestation.signature,
    )
```

## Beacon chain state transition function

*Note*: state transition is fundamentally modified in EIP-7732. The full state
transition is broken in two parts, first importing a signed block and then
importing an execution payload.

The post-state corresponding to a pre-state `state` and a signed beacon block
`signed_block` is defined as `state_transition(state, signed_block)`. State
transitions that trigger an unhandled exception (e.g. a failed `assert` or an
out-of-range list access) are considered invalid. State transitions that cause a
`uint64` overflow or underflow are also considered invalid.

The post-state corresponding to a pre-state `state` and a signed execution
payload envelope `signed_envelope` is defined as
`process_execution_payload(state, signed_envelope)`. State transitions that
trigger an unhandled exception (e.g. a failed `assert` or an out-of-range list
access) are considered invalid. State transitions that cause an `uint64`
overflow or underflow are also considered invalid.

### Modified `process_slot`

*Note*: `process_slot` is modified to unset the payload availability bit.

```python
def process_slot(state: BeaconState) -> None:
    # Cache state root
    previous_state_root = hash_tree_root(state)
    state.state_roots[state.slot % SLOTS_PER_HISTORICAL_ROOT] = previous_state_root
    # Cache latest block header state root
    if state.latest_block_header.state_root == Bytes32():
        state.latest_block_header.state_root = previous_state_root
    # Cache block root
    previous_block_root = hash_tree_root(state.latest_block_header)
    state.block_roots[state.slot % SLOTS_PER_HISTORICAL_ROOT] = previous_block_root
    # [New in EIP7732]
    # Unset the next payload availability
    state.execution_payload_availability[(state.slot + 1) % SLOTS_PER_HISTORICAL_ROOT] = 0b0
```

### Epoch processing

#### Modified `process_epoch`

*Note*: The function `process_epoch` is modified to process the builder
payments.

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
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
    # [New in EIP7732]
    process_builder_pending_payments(state)
```

#### New `process_builder_pending_payments`

```python
def process_builder_pending_payments(state: BeaconState) -> None:
    """
    Processes the builder pending payments from the previous epoch.
    """
    quorum = (
        get_total_active_balance(state) // SLOTS_PER_EPOCH * BUILDER_PAYMENT_THRESHOLD_NUMERATOR
    )
    quorum //= BUILDER_PAYMENT_THRESHOLD_DENOMINATOR
    for payment in state.builder_pending_payments[:SLOTS_PER_EPOCH]:
        if payment.weight > quorum:
            exit_queue_epoch = compute_exit_epoch_and_update_churn(state, payment.withdrawal.amount)
            payment.withdrawal.withdrawable_epoch = Epoch(
                exit_queue_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
            )
            state.builder_pending_withdrawals.append(payment.withdrawal)
    state.builder_pending_payments = state.builder_pending_payments[SLOTS_PER_EPOCH:] + [
        BuilderPendingPayment() for _ in range(SLOTS_PER_EPOCH)
    ]
```

### Block processing

*Note*: The function `process_block` is modified to call the new and updated
functions and removes the call to `process_execution_payload`.

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    # [Modified in EIP7732]
    process_withdrawals(state)
    # [Modified in EIP7732]
    # Removed `process_execution_payload`
    # [New in EIP7732]
    process_execution_payload_header(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    # [Modified in EIP7732]
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### Withdrawals

##### New `is_builder_payment_withdrawable`

```python
def is_builder_payment_withdrawable(
    state: BeaconState, withdrawal: BuilderPendingWithdrawal
) -> bool:
    """
    Check if the builder is slashed and not yet withdrawable.
    """
    builder = state.validators[withdrawal.builder_index]
    current_epoch = compute_epoch_at_slot(state.slot)
    return builder.withdrawable_epoch >= current_epoch or not builder.slashed
```

##### Modified `get_expected_withdrawals`

*Note*: The function `get_expected_withdrawals` is modified to include builder
payments.

```python
def get_expected_withdrawals(state: BeaconState) -> Tuple[Sequence[Withdrawal], uint64, uint64]:
    epoch = get_current_epoch(state)
    withdrawal_index = state.next_withdrawal_index
    validator_index = state.next_withdrawal_validator_index
    withdrawals: List[Withdrawal] = []
    processed_partial_withdrawals_count = 0
    processed_builder_withdrawals_count = 0

    # [New in EIP7732]
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
                    amount=balance - get_max_effective_balance(validator),
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

##### Modified `process_withdrawals`

*Note*: This is modified to take only the `state` as parameter. Withdrawals are
deterministic given the beacon state, any execution payload that has the
corresponding block as parent beacon block is required to honor these
withdrawals in the execution layer. This function must be called before
`process_execution_payload_header` as this latter function affects validator
balances.

```python
def process_withdrawals(state: BeaconState) -> None:
    # return early if the parent block was empty
    if not is_parent_block_full(state):
        return

    withdrawals, processed_builder_withdrawals_count, processed_partial_withdrawals_count = (
        get_expected_withdrawals(state)
    )
    withdrawals_list = List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD](withdrawals)
    state.latest_withdrawals_root = hash_tree_root(withdrawals_list)
    for withdrawal in withdrawals:
        decrease_balance(state, withdrawal.validator_index, withdrawal.amount)

    # Update the pending builder withdrawals
    state.builder_pending_withdrawals = [
        w
        for w in state.builder_pending_withdrawals[:processed_builder_withdrawals_count]
        if not is_builder_payment_withdrawable(state, w)
    ] + state.builder_pending_withdrawals[processed_builder_withdrawals_count:]

    # Update pending partial withdrawals
    state.pending_partial_withdrawals = state.pending_partial_withdrawals[
        processed_partial_withdrawals_count:
    ]

    # Update the next withdrawal index if this block contained withdrawals
    if len(withdrawals) != 0:
        latest_withdrawal = withdrawals[-1]
        state.next_withdrawal_index = WithdrawalIndex(latest_withdrawal.index + 1)

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

#### Execution payload header

##### New `verify_execution_payload_header_signature`

```python
def verify_execution_payload_header_signature(
    state: BeaconState, signed_header: SignedExecutionPayloadHeader
) -> bool:
    # Check the signature
    builder = state.validators[signed_header.message.builder_index]
    signing_root = compute_signing_root(
        signed_header.message, get_domain(state, DOMAIN_BEACON_BUILDER)
    )
    return bls.Verify(builder.pubkey, signing_root, signed_header.signature)
```

##### New `process_execution_payload_header`

```python
def process_execution_payload_header(state: BeaconState, block: BeaconBlock) -> None:
    # Verify the header signature
    signed_header = block.body.signed_execution_payload_header
    assert verify_execution_payload_header_signature(state, signed_header)

    header = signed_header.message
    builder_index = header.builder_index
    builder = state.validators[builder_index]
    assert is_active_validator(builder, get_current_epoch(state))
    assert not builder.slashed
    amount = header.value
    # For self-builds, amount must be zero regardless of withdrawal credential prefix
    if builder_index == block.proposer_index:
        assert amount == 0
    else:
        # Non-self builds require builder withdrawal credential
        assert has_builder_withdrawal_credential(builder)

    # Check that the builder is active, non-slashed, and has funds to cover the bid
    pending_payments = sum(
        payment.withdrawal.amount
        for payment in state.builder_pending_payments
        if payment.withdrawal.builder_index == builder_index
    )
    pending_withdrawals = sum(
        withdrawal.amount
        for withdrawal in state.builder_pending_withdrawals
        if withdrawal.builder_index == builder_index
    )
    assert (
        amount == 0
        or state.balances[builder_index]
        >= amount + pending_payments + pending_withdrawals + MIN_ACTIVATION_BALANCE
    )

    # Verify that the bid is for the current slot
    assert header.slot == block.slot
    # Verify that the bid is for the right parent block
    assert header.parent_block_hash == state.latest_block_hash
    assert header.parent_block_root == block.parent_root

    # Record the pending payment
    pending_payment = BuilderPendingPayment(
        weight=0,
        withdrawal=BuilderPendingWithdrawal(
            fee_recipient=header.fee_recipient,
            amount=amount,
            builder_index=builder_index,
        ),
    )
    state.builder_pending_payments[SLOTS_PER_EPOCH + header.slot % SLOTS_PER_EPOCH] = (
        pending_payment
    )

    # Cache the signed execution payload header
    state.latest_execution_payload_header = header
```

#### Operations

##### Modified `process_operations`

*Note*: `process_operations` is modified to process PTC attestations and removes
calls to `process_deposit_request`, `process_withdrawal_request`, and
`process_consolidation_request`.

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
    # [Modified in EIP7732]
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    # [Modified in EIP7732]
    # Removed `process_deposit_request`
    # [Modified in EIP7732]
    # Removed `process_withdrawal_request`
    # [Modified in EIP7732]
    # Removed `process_consolidation_request`
    # [New in EIP7732]
    for_ops(body.payload_attestations, process_payload_attestation)
```

##### Attestations

###### Modified `process_attestation`

*Note*: The function is modified to track the weight for pending builder
payments and to use the `index` field in the `AttestationData` to signal the
payload availability.

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.target.epoch == compute_epoch_at_slot(data.slot)
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot

    # [Modified in EIP7732]
    assert data.index < 2
    committee_indices = get_committee_indices(attestation.committee_bits)
    committee_offset = 0
    for committee_index in committee_indices:
        assert committee_index < get_committee_count_per_slot(state, data.target.epoch)
        committee = get_beacon_committee(state, data.slot, committee_index)
        committee_attesters = set(
            attester_index
            for i, attester_index in enumerate(committee)
            if attestation.aggregation_bits[committee_offset + i]
        )
        assert len(committee_attesters) > 0
        committee_offset += len(committee)

    # Bitfield length matches total number of participants
    assert len(attestation.aggregation_bits) == committee_offset

    # Participation flag indices
    participation_flag_indices = get_attestation_participation_flag_indices(
        state, data, state.slot - data.slot
    )

    # Verify signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))

    # Update epoch participation flags
    current_epoch_target = True
    if data.target.epoch == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
        payment = state.builder_pending_payments[SLOTS_PER_EPOCH + data.slot % SLOTS_PER_EPOCH]
    else:
        epoch_participation = state.previous_epoch_participation
        payment = state.builder_pending_payments[data.slot % SLOTS_PER_EPOCH]
        current_epoch_target = False

    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, attestation):
        for flag_index, weight in enumerate(PARTICIPATION_FLAG_WEIGHTS):
            if flag_index in participation_flag_indices and not has_flag(
                epoch_participation[index], flag_index
            ):
                epoch_participation[index] = add_flag(epoch_participation[index], flag_index)
                proposer_reward_numerator += get_base_reward(state, index) * weight
                # [New in EIP7732]
                # Update the builder payment weight
                if flag_index == TIMELY_HEAD_FLAG_INDEX and is_attestation_same_slot(state, data):
                    payment.weight += state.validators[index].effective_balance

    # Reward proposer
    proposer_reward_denominator = (
        (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT) * WEIGHT_DENOMINATOR // PROPOSER_WEIGHT
    )
    proposer_reward = Gwei(proposer_reward_numerator // proposer_reward_denominator)
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
    # Update builder payment weight

    if current_epoch_target:
        state.builder_pending_payments[SLOTS_PER_EPOCH + data.slot % SLOTS_PER_EPOCH] = payment
    else:
        state.builder_pending_payments[data.slot % SLOTS_PER_EPOCH] = payment
```

##### Payload Attestations

###### New `process_payload_attestation`

```python
def process_payload_attestation(
    state: BeaconState, payload_attestation: PayloadAttestation
) -> None:
    # Check that the attestation is for the parent beacon block
    data = payload_attestation.data
    assert data.beacon_block_root == state.latest_block_header.parent_root
    # Check that the attestation is for the previous slot
    assert data.slot + 1 == state.slot

    # Verify signature
    indexed_payload_attestation = get_indexed_payload_attestation(
        state, data.slot, payload_attestation
    )
    assert is_valid_indexed_payload_attestation(state, indexed_payload_attestation)
```

#### Modified `is_merge_transition_complete`

`is_merge_transition_complete` is modified only for testing purposes to add the
blob kzg commitments root for an empty list

```python
def is_merge_transition_complete(state: BeaconState) -> bool:
    header = ExecutionPayloadHeader()
    kzgs = List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]()
    header.blob_kzg_commitments_root = kzgs.hash_tree_root()

    return state.latest_execution_payload_header != header
```

#### Modified `validate_merge_block`

`validate_merge_block` is modified to use the new
`signed_execution_payload_header` message in the Beacon Block Body

```python
def validate_merge_block(block: BeaconBlock) -> None:
    """
    Check the parent PoW block of execution payload is a valid terminal PoW block.

    Note: Unavailable PoW block(s) may later become available,
    and a client software MAY delay a call to ``validate_merge_block``
    until the PoW block(s) become available.
    """
    if TERMINAL_BLOCK_HASH != Hash32():
        # If `TERMINAL_BLOCK_HASH` is used as an override, the activation epoch must be reached.
        assert compute_epoch_at_slot(block.slot) >= TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH
        assert (
            block.body.signed_execution_payload_header.message.parent_block_hash
            == TERMINAL_BLOCK_HASH
        )
        return

    # [Modified in EIP7732]
    pow_block = get_pow_block(block.body.signed_execution_payload_header.message.parent_block_hash)
    # Check if `pow_block` is available
    assert pow_block is not None
    pow_parent = get_pow_block(pow_block.parent_hash)
    # Check if `pow_parent` is available
    assert pow_parent is not None
    # Check if `pow_block` is a valid terminal PoW block
    assert is_valid_terminal_pow_block(pow_block, pow_parent)
```

### Execution payload processing

#### New `verify_execution_payload_envelope_signature`

```python
def verify_execution_payload_envelope_signature(
    state: BeaconState, signed_envelope: SignedExecutionPayloadEnvelope
) -> bool:
    builder = state.validators[signed_envelope.message.builder_index]
    signing_root = compute_signing_root(
        signed_envelope.message, get_domain(state, DOMAIN_BEACON_BUILDER)
    )
    return bls.Verify(builder.pubkey, signing_root, signed_envelope.signature)
```

#### New `process_execution_payload`

*Note*: `process_execution_payload` is now an independent check in state
transition. It is called when importing a signed execution payload proposed by
the builder of the current slot.

```python
def process_execution_payload(
    state: BeaconState,
    signed_envelope: SignedExecutionPayloadEnvelope,
    execution_engine: ExecutionEngine,
    verify: bool = True,
) -> None:
    # Verify signature
    if verify:
        assert verify_execution_payload_envelope_signature(state, signed_envelope)
    envelope = signed_envelope.message
    payload = envelope.payload
    # Cache latest block header state root
    previous_state_root = hash_tree_root(state)
    if state.latest_block_header.state_root == Root():
        state.latest_block_header.state_root = previous_state_root

    # Verify consistency with the beacon block
    assert envelope.beacon_block_root == hash_tree_root(state.latest_block_header)
    assert envelope.slot == state.slot

    # Verify consistency with the committed header
    committed_header = state.latest_execution_payload_header
    assert envelope.builder_index == committed_header.builder_index
    assert committed_header.blob_kzg_commitments_root == hash_tree_root(
        envelope.blob_kzg_commitments
    )

    # Verify the withdrawals root
    assert hash_tree_root(payload.withdrawals) == state.latest_withdrawals_root

    # Verify the gas_limit
    assert committed_header.gas_limit == payload.gas_limit
    # Verify the block hash
    assert committed_header.block_hash == payload.block_hash
    # Verify consistency of the parent hash with respect to the previous execution payload
    assert payload.parent_hash == state.latest_block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_time_at_slot(state, state.slot)
    # Verify commitments are under limit
    assert len(envelope.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK
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

    # Queue the builder payment
    payment = state.builder_pending_payments[SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH]
    exit_queue_epoch = compute_exit_epoch_and_update_churn(state, payment.withdrawal.amount)
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
    state.latest_full_slot = state.slot

    # Verify the state root
    if verify:
        assert envelope.state_root == hash_tree_root(state)
```
