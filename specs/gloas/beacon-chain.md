# Gloas -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Domain types](#domain-types)
  - [Misc](#misc)
  - [Withdrawal prefixes](#withdrawal-prefixes)
- [Preset](#preset)
  - [Misc](#misc-1)
  - [Max operations per block](#max-operations-per-block)
  - [State list lengths](#state-list-lengths)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`BuilderPendingPayment`](#builderpendingpayment)
    - [`BuilderPendingWithdrawal`](#builderpendingwithdrawal)
    - [`PayloadAttestationData`](#payloadattestationdata)
    - [`PayloadAttestation`](#payloadattestation)
    - [`PayloadAttestationMessage`](#payloadattestationmessage)
    - [`IndexedPayloadAttestation`](#indexedpayloadattestation)
    - [`ExecutionPayloadBid`](#executionpayloadbid)
    - [`SignedExecutionPayloadBid`](#signedexecutionpayloadbid)
    - [`ExecutionPayloadEnvelope`](#executionpayloadenvelope)
    - [`SignedExecutionPayloadEnvelope`](#signedexecutionpayloadenvelope)
  - [Modified containers](#modified-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
- [Helper functions](#helper-functions)
  - [Predicates](#predicates)
    - [New `is_builder_withdrawal_credential`](#new-is_builder_withdrawal_credential)
    - [New `has_builder_withdrawal_credential`](#new-has_builder_withdrawal_credential)
    - [Modified `has_compounding_withdrawal_credential`](#modified-has_compounding_withdrawal_credential)
    - [New `is_attestation_same_slot`](#new-is_attestation_same_slot)
    - [New `is_valid_indexed_payload_attestation`](#new-is_valid_indexed_payload_attestation)
    - [New `is_parent_block_full`](#new-is_parent_block_full)
  - [Misc](#misc-2)
    - [Modified `get_pending_balance_to_withdraw`](#modified-get_pending_balance_to_withdraw)
    - [New `compute_balance_weighted_selection`](#new-compute_balance_weighted_selection)
    - [New `compute_balance_weighted_acceptance`](#new-compute_balance_weighted_acceptance)
    - [Modified `compute_proposer_indices`](#modified-compute_proposer_indices)
  - [Beacon State accessors](#beacon-state-accessors)
    - [Modified `get_next_sync_committee_indices`](#modified-get_next_sync_committee_indices)
    - [Modified `get_attestation_participation_flag_indices`](#modified-get_attestation_participation_flag_indices)
    - [New `get_ptc`](#new-get_ptc)
    - [New `get_indexed_payload_attestation`](#new-get_indexed_payload_attestation)
    - [New `get_builder_payment_quorum_threshold`](#new-get_builder_payment_quorum_threshold)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Modified `process_slot`](#modified-process_slot)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [New `process_builder_pending_payments`](#new-process_builder_pending_payments)
  - [Block processing](#block-processing)
    - [Withdrawals](#withdrawals)
      - [New `is_builder_payment_withdrawable`](#new-is_builder_payment_withdrawable)
      - [New `get_builder_withdrawable_balance`](#new-get_builder_withdrawable_balance)
      - [New `get_builder_withdrawals`](#new-get_builder_withdrawals)
      - [Modified `get_expected_withdrawals`](#modified-get_expected_withdrawals)
      - [New `update_payload_expected_withdrawals`](#new-update_payload_expected_withdrawals)
      - [New `update_builder_pending_withdrawals`](#new-update_builder_pending_withdrawals)
      - [Modified `process_withdrawals`](#modified-process_withdrawals)
    - [Execution payload bid](#execution-payload-bid)
      - [New `verify_execution_payload_bid_signature`](#new-verify_execution_payload_bid_signature)
      - [New `process_execution_payload_bid`](#new-process_execution_payload_bid)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [Attestations](#attestations)
        - [Modified `process_attestation`](#modified-process_attestation)
      - [Payload Attestations](#payload-attestations)
        - [New `process_payload_attestation`](#new-process_payload_attestation)
      - [Proposer Slashing](#proposer-slashing)
        - [Modified `process_proposer_slashing`](#modified-process_proposer_slashing)
  - [Execution payload processing](#execution-payload-processing)
    - [New `verify_execution_payload_envelope_signature`](#new-verify_execution_payload_envelope_signature)
    - [New `process_execution_payload`](#new-process_execution_payload)

<!-- mdformat-toc end -->

## Introduction

Gloas is a consensus-layer upgrade containing a number of features. Including:

- [EIP-7732](https://eips.ethereum.org/EIPS/eip-7732): Enshrined
  Proposer-Builder Separation

*Note*: This specification is built upon [Fulu](../fulu/beacon-chain.md).

## Constants

### Domain types

| Name                    | Value                      |
| ----------------------- | -------------------------- |
| `DOMAIN_BEACON_BUILDER` | `DomainType('0x0B000000')` |
| `DOMAIN_PTC_ATTESTER`   | `DomainType('0x0C000000')` |

### Misc

| Name                                    | Value        |
| --------------------------------------- | ------------ |
| `BUILDER_PAYMENT_THRESHOLD_NUMERATOR`   | `uint64(6)`  |
| `BUILDER_PAYMENT_THRESHOLD_DENOMINATOR` | `uint64(10)` |

### Withdrawal prefixes

| Name                        | Value            | Description                                |
| --------------------------- | ---------------- | ------------------------------------------ |
| `BUILDER_WITHDRAWAL_PREFIX` | `Bytes1('0x03')` | Withdrawal credential prefix for a builder |

## Preset

### Misc

| Name       | Value                  |
| ---------- | ---------------------- |
| `PTC_SIZE` | `uint64(2**9)` (= 512) |

### Max operations per block

| Name                       | Value |
| -------------------------- | ----- |
| `MAX_PAYLOAD_ATTESTATIONS` | `4`   |

### State list lengths

| Name                                | Value                         | Unit                        |
| ----------------------------------- | ----------------------------- | --------------------------- |
| `BUILDER_PENDING_WITHDRAWALS_LIMIT` | `uint64(2**20)` (= 1,048,576) | Builder pending withdrawals |

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

#### `ExecutionPayloadBid`

```python
class ExecutionPayloadBid(Container):
    parent_block_hash: Hash32
    parent_block_root: Root
    block_hash: Hash32
    prev_randao: Bytes32
    fee_recipient: ExecutionAddress
    gas_limit: uint64
    builder_index: ValidatorIndex
    slot: Slot
    value: Gwei
    execution_payment: Gwei
    blob_kzg_commitments_root: Root
```

#### `SignedExecutionPayloadBid`

```python
class SignedExecutionPayloadBid(Container):
    message: ExecutionPayloadBid
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

*Note*: The removed fields (`execution_payload`, `blob_kzg_commitments`, and
`execution_requests`) now exist in `ExecutionPayloadEnvelope`.

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
    # [Modified in Gloas:EIP7732]
    # Removed `execution_payload`
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    # [Modified in Gloas:EIP7732]
    # Removed `blob_kzg_commitments`
    # [Modified in Gloas:EIP7732]
    # Removed `execution_requests`
    # [New in Gloas:EIP7732]
    signed_execution_payload_bid: SignedExecutionPayloadBid
    # [New in Gloas:EIP7732]
    payload_attestations: List[PayloadAttestation, MAX_PAYLOAD_ATTESTATIONS]
```

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
    # [Modified in Gloas:EIP7732]
    # Removed `latest_execution_payload_header`
    # [New in Gloas:EIP7732]
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
    # [New in Gloas:EIP7732]
    execution_payload_availability: Bitvector[SLOTS_PER_HISTORICAL_ROOT]
    # [New in Gloas:EIP7732]
    builder_pending_payments: Vector[BuilderPendingPayment, 2 * SLOTS_PER_EPOCH]
    # [New in Gloas:EIP7732]
    builder_pending_withdrawals: List[BuilderPendingWithdrawal, BUILDER_PENDING_WITHDRAWALS_LIMIT]
    # [New in Gloas:EIP7732]
    latest_block_hash: Hash32
    # [New in Gloas:EIP7732]
    payload_expected_withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
```

## Helper functions

### Predicates

#### New `is_builder_withdrawal_credential`

```python
def is_builder_withdrawal_credential(withdrawal_credentials: Bytes32) -> bool:
    return withdrawal_credentials[:1] == BUILDER_WITHDRAWAL_PREFIX
```

#### New `has_builder_withdrawal_credential`

```python
def has_builder_withdrawal_credential(validator: Validator) -> bool:
    """
    Check if ``validator`` has an 0x03 prefixed "builder" withdrawal credential.
    """
    return is_builder_withdrawal_credential(validator.withdrawal_credentials)
```

#### Modified `has_compounding_withdrawal_credential`

*Note*: The function `has_compounding_withdrawal_credential` is modified to
return true for builders.

```python
def has_compounding_withdrawal_credential(validator: Validator) -> bool:
    """
    Check if ``validator`` has an 0x02 or 0x03 prefixed withdrawal credential.
    """
    if is_compounding_withdrawal_credential(validator.withdrawal_credentials):
        return True
    if is_builder_withdrawal_credential(validator.withdrawal_credentials):
        return True
    return False
```

#### New `is_attestation_same_slot`

```python
def is_attestation_same_slot(state: BeaconState, data: AttestationData) -> bool:
    """
    Check if the attestation is for the block proposed at the attestation slot.
    """
    if data.slot == 0:
        return True

    blockroot = data.beacon_block_root
    slot_blockroot = get_block_root_at_slot(state, data.slot)
    prev_blockroot = get_block_root_at_slot(state, Slot(data.slot - 1))

    return blockroot == slot_blockroot and blockroot != prev_blockroot
```

#### New `is_valid_indexed_payload_attestation`

```python
def is_valid_indexed_payload_attestation(
    state: BeaconState, indexed_payload_attestation: IndexedPayloadAttestation
) -> bool:
    """
    Check if ``indexed_payload_attestation`` is non-empty, has sorted indices, and has
    a valid aggregate signature.
    """
    # Verify indices are non-empty and sorted
    indices = indexed_payload_attestation.attesting_indices
    if len(indices) == 0 or not indices == sorted(indices):
        return False

    # Verify aggregate signature
    pubkeys = [state.validators[i].pubkey for i in indices]
    domain = get_domain(state, DOMAIN_PTC_ATTESTER, None)
    signing_root = compute_signing_root(indexed_payload_attestation.data, domain)
    return bls.FastAggregateVerify(pubkeys, signing_root, indexed_payload_attestation.signature)
```

#### New `is_parent_block_full`

*Note*: This function returns true if the last committed payload bid was
fulfilled with a payload, which can only happen when both beacon block and
payload were present. This function must be called on a beacon state before
processing the execution payload bid in the block.

```python
def is_parent_block_full(state: BeaconState) -> bool:
    return state.latest_execution_payload_bid.block_hash == state.latest_block_hash
```

### Misc

#### Modified `get_pending_balance_to_withdraw`

*Note*: `get_pending_balance_to_withdraw` is modified to account for pending
builder payments.

```python
def get_pending_balance_to_withdraw(state: BeaconState, validator_index: ValidatorIndex) -> Gwei:
    return (
        sum(
            withdrawal.amount
            for withdrawal in state.pending_partial_withdrawals
            if withdrawal.validator_index == validator_index
        )
        # [New in Gloas:EIP7732]
        + sum(
            withdrawal.amount
            for withdrawal in state.builder_pending_withdrawals
            if withdrawal.builder_index == validator_index
        )
        # [New in Gloas:EIP7732]
        + sum(
            payment.withdrawal.amount
            for payment in state.builder_pending_payments
            if payment.withdrawal.builder_index == validator_index
        )
    )
```

#### New `compute_balance_weighted_selection`

```python
def compute_balance_weighted_selection(
    state: BeaconState,
    indices: Sequence[ValidatorIndex],
    seed: Bytes32,
    size: uint64,
    shuffle_indices: bool,
) -> Sequence[ValidatorIndex]:
    """
    Return ``size`` indices sampled by effective balance, using ``indices``
    as candidates. If ``shuffle_indices`` is ``True``, candidate indices
    are themselves sampled from ``indices`` by shuffling it, otherwise
    ``indices`` is traversed in order.
    """
    total = uint64(len(indices))
    assert total > 0
    selected: List[ValidatorIndex] = []
    i = uint64(0)
    while len(selected) < size:
        next_index = i % total
        if shuffle_indices:
            next_index = compute_shuffled_index(next_index, total, seed)
        candidate_index = indices[next_index]
        if compute_balance_weighted_acceptance(state, candidate_index, seed, i):
            selected.append(candidate_index)
        i += 1
    return selected
```

#### New `compute_balance_weighted_acceptance`

```python
def compute_balance_weighted_acceptance(
    state: BeaconState, index: ValidatorIndex, seed: Bytes32, i: uint64
) -> bool:
    """
    Return whether to accept the selection of the validator ``index``, with probability
    proportional to its ``effective_balance``, and randomness given by ``seed`` and ``i``.
    """
    MAX_RANDOM_VALUE = 2**16 - 1
    random_bytes = hash(seed + uint_to_bytes(i // 16))
    offset = i % 16 * 2
    random_value = bytes_to_uint64(random_bytes[offset : offset + 2])
    effective_balance = state.validators[index].effective_balance
    return effective_balance * MAX_RANDOM_VALUE >= MAX_EFFECTIVE_BALANCE_ELECTRA * random_value
```

#### Modified `compute_proposer_indices`

*Note*: `compute_proposer_indices` is modified to use
`compute_balance_weighted_selection` as a helper for the balance-weighted
sampling process.

```python
def compute_proposer_indices(
    state: BeaconState, epoch: Epoch, seed: Bytes32, indices: Sequence[ValidatorIndex]
) -> Vector[ValidatorIndex, SLOTS_PER_EPOCH]:
    """
    Return the proposer indices for the given ``epoch``.
    """
    start_slot = compute_start_slot_at_epoch(epoch)
    seeds = [hash(seed + uint_to_bytes(Slot(start_slot + i))) for i in range(SLOTS_PER_EPOCH)]
    # [Modified in Gloas:EIP7732]
    return [
        compute_balance_weighted_selection(state, indices, seed, size=1, shuffle_indices=True)[0]
        for seed in seeds
    ]
```

### Beacon State accessors

#### Modified `get_next_sync_committee_indices`

*Note*: `get_next_sync_committee_indices` is modified to use
`compute_balance_weighted_selection` as a helper for the balance-weighted
sampling process.

```python
def get_next_sync_committee_indices(state: BeaconState) -> Sequence[ValidatorIndex]:
    """
    Return the sync committee indices, with possible duplicates, for the next sync committee.
    """
    epoch = Epoch(get_current_epoch(state) + 1)
    seed = get_seed(state, epoch, DOMAIN_SYNC_COMMITTEE)
    indices = get_active_validator_indices(state, epoch)
    return compute_balance_weighted_selection(
        state, indices, seed, size=SYNC_COMMITTEE_SIZE, shuffle_indices=True
    )
```

#### Modified `get_attestation_participation_flag_indices`

*Note*: The function `get_attestation_participation_flag_indices` is modified to
include a new payload matching constraint to `is_matching_head`.

```python
def get_attestation_participation_flag_indices(
    state: BeaconState, data: AttestationData, inclusion_delay: uint64
) -> Sequence[int]:
    """
    Return the flag indices that are satisfied by an attestation.
    """
    # Matching source
    if data.target.epoch == get_current_epoch(state):
        justified_checkpoint = state.current_justified_checkpoint
    else:
        justified_checkpoint = state.previous_justified_checkpoint
    is_matching_source = data.source == justified_checkpoint

    # Matching target
    target_root = get_block_root(state, data.target.epoch)
    target_root_matches = data.target.root == target_root
    is_matching_target = is_matching_source and target_root_matches

    # [New in Gloas:EIP7732]
    if is_attestation_same_slot(state, data):
        assert data.index == 0
        payload_matches = True
    else:
        slot_index = data.slot % SLOTS_PER_HISTORICAL_ROOT
        payload_index = state.execution_payload_availability[slot_index]
        payload_matches = data.index == payload_index

    # Matching head
    head_root = get_block_root_at_slot(state, data.slot)
    head_root_matches = data.beacon_block_root == head_root
    # [Modified in Gloas:EIP7732]
    is_matching_head = is_matching_target and head_root_matches and payload_matches

    assert is_matching_source

    participation_flag_indices = []
    if is_matching_source and inclusion_delay <= integer_squareroot(SLOTS_PER_EPOCH):
        participation_flag_indices.append(TIMELY_SOURCE_FLAG_INDEX)
    if is_matching_target:
        participation_flag_indices.append(TIMELY_TARGET_FLAG_INDEX)
    if is_matching_head and inclusion_delay == MIN_ATTESTATION_INCLUSION_DELAY:
        participation_flag_indices.append(TIMELY_HEAD_FLAG_INDEX)

    return participation_flag_indices
```

#### New `get_ptc`

```python
def get_ptc(state: BeaconState, slot: Slot) -> Vector[ValidatorIndex, PTC_SIZE]:
    """
    Get the payload timeliness committee for the given ``slot``.
    """
    epoch = compute_epoch_at_slot(slot)
    seed = hash(get_seed(state, epoch, DOMAIN_PTC_ATTESTER) + uint_to_bytes(slot))
    indices: List[ValidatorIndex] = []
    # Concatenate all committees for this slot in order
    committees_per_slot = get_committee_count_per_slot(state, epoch)
    for i in range(committees_per_slot):
        committee = get_beacon_committee(state, slot, CommitteeIndex(i))
        indices.extend(committee)
    return compute_balance_weighted_selection(
        state, indices, seed, size=PTC_SIZE, shuffle_indices=False
    )
```

#### New `get_indexed_payload_attestation`

```python
def get_indexed_payload_attestation(
    state: BeaconState, slot: Slot, payload_attestation: PayloadAttestation
) -> IndexedPayloadAttestation:
    """
    Return the indexed payload attestation corresponding to ``payload_attestation``.
    """
    ptc = get_ptc(state, slot)
    bits = payload_attestation.aggregation_bits
    attesting_indices = [index for i, index in enumerate(ptc) if bits[i]]

    return IndexedPayloadAttestation(
        attesting_indices=sorted(attesting_indices),
        data=payload_attestation.data,
        signature=payload_attestation.signature,
    )
```

#### New `get_builder_payment_quorum_threshold`

```python
def get_builder_payment_quorum_threshold(state: BeaconState) -> uint64:
    """
    Calculate the quorum threshold for builder payments.
    """
    per_slot_balance = get_total_active_balance(state) // SLOTS_PER_EPOCH
    quorum = per_slot_balance * BUILDER_PAYMENT_THRESHOLD_NUMERATOR
    return uint64(quorum // BUILDER_PAYMENT_THRESHOLD_DENOMINATOR)
```

## Beacon chain state transition function

State transition is fundamentally modified in Gloas. The full state transition
is broken in two parts, first importing a signed block and then importing an
execution payload.

The post-state corresponding to a pre-state `state` and a signed beacon block
`signed_block` is defined as `state_transition(state, signed_block)`. State
transitions that trigger an unhandled exception (e.g. a failed `assert` or an
out-of-range list access) are considered invalid. State transitions that cause a
`uint64` overflow or underflow are also considered invalid.

The post-state corresponding to a pre-state `state` and a signed execution
payload envelope `signed_envelope` is defined as
`process_execution_payload(state, signed_envelope, execution_engine)`. State
transitions that trigger an unhandled exception (e.g. a failed `assert` or an
out-of-range list access) are considered invalid. State transitions that cause
an `uint64` overflow or underflow are also considered invalid.

### Modified `process_slot`

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
    # [New in Gloas:EIP7732]
    # Unset the next payload availability
    state.execution_payload_availability[(state.slot + 1) % SLOTS_PER_HISTORICAL_ROOT] = 0b0
```

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
    # [New in Gloas:EIP7732]
    process_builder_pending_payments(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
    process_proposer_lookahead(state)
```

#### New `process_builder_pending_payments`

```python
def process_builder_pending_payments(state: BeaconState) -> None:
    """
    Processes the builder pending payments from the previous epoch.
    """
    quorum = get_builder_payment_quorum_threshold(state)
    for payment in state.builder_pending_payments[:SLOTS_PER_EPOCH]:
        if payment.weight >= quorum:
            amount = payment.withdrawal.amount
            exit_queue_epoch = compute_exit_epoch_and_update_churn(state, amount)
            withdrawable_epoch = exit_queue_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
            payment.withdrawal.withdrawable_epoch = Epoch(withdrawable_epoch)
            state.builder_pending_withdrawals.append(payment.withdrawal)

    old_payments = state.builder_pending_payments[SLOTS_PER_EPOCH:]
    new_payments = [BuilderPendingPayment() for _ in range(SLOTS_PER_EPOCH)]
    state.builder_pending_payments = old_payments + new_payments
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    # [Modified in Gloas:EIP7732]
    process_withdrawals(state)
    # [Modified in Gloas:EIP7732]
    # Removed `process_execution_payload`
    # [New in Gloas:EIP7732]
    process_execution_payload_bid(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    # [Modified in Gloas:EIP7732]
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### Withdrawals

##### New `is_builder_payment_withdrawable`

*Note*: Builder payments are immediately withdrawable if the builder is not
slashed; this allows the builder to submit bids as soon as it becomes active. On
the other hand, if the builder is slashed, builder payments cannot be made until
after the builder's withdrawable epoch (which is set by the `slash_validator`
function); this is a security measure to prevent a slashed builder from sending
its stake to a colluding proposer before the appropriate penalties are applied.

```python
def is_builder_payment_withdrawable(
    state: BeaconState, withdrawal: BuilderPendingWithdrawal
) -> bool:
    """
    Check if a builder payment is withdrawable.
    """
    builder = state.validators[withdrawal.builder_index]
    current_epoch = compute_epoch_at_slot(state.slot)
    return not builder.slashed or current_epoch >= builder.withdrawable_epoch
```

##### New `get_builder_withdrawable_balance`

```python
def get_builder_withdrawable_balance(builder: Validator, balance: Gwei) -> Gwei:
    """
    Get the withdrawable balance for a builder payment.
    """
    if builder.slashed:
        return balance
    elif balance > MIN_ACTIVATION_BALANCE:
        return balance - MIN_ACTIVATION_BALANCE
    else:
        return Gwei(0)
```

##### New `get_builder_withdrawals`

```python
def get_builder_withdrawals(
    state: BeaconState,
    withdrawal_index: WithdrawalIndex,
    epoch: Epoch,
    prior_withdrawals: Sequence[Withdrawal],
) -> Tuple[Sequence[Withdrawal], WithdrawalIndex, uint64]:
    withdrawals_limit = MAX_WITHDRAWALS_PER_PAYLOAD - 1

    processed_count: uint64 = 0
    withdrawals: List[Withdrawal] = []
    for withdrawal in state.builder_pending_withdrawals:
        all_withdrawals = prior_withdrawals + withdrawals
        is_withdrawable = withdrawal.withdrawable_epoch <= epoch
        has_reached_limit = len(all_withdrawals) == withdrawals_limit
        if not is_withdrawable or has_reached_limit:
            break

        if is_builder_payment_withdrawable(state, withdrawal):
            builder_index = withdrawal.builder_index
            builder = state.validators[builder_index]
            balance = get_balance_after_withdrawals(state, builder_index, all_withdrawals)
            withdrawable_balance = get_builder_withdrawable_balance(builder, balance)
            withdrawal_amount = min(withdrawable_balance, withdrawal.amount)
            if withdrawal_amount > 0:
                withdrawals.append(
                    Withdrawal(
                        index=withdrawal_index,
                        validator_index=builder_index,
                        address=withdrawal.fee_recipient,
                        amount=withdrawal_amount,
                    )
                )
                withdrawal_index += WithdrawalIndex(1)

        processed_count += 1

    return withdrawals, withdrawal_index, processed_count
```

##### Modified `get_expected_withdrawals`

```python
def get_expected_withdrawals(
    state: BeaconState,
) -> Tuple[Sequence[Withdrawal], uint64, uint64, uint64]:
    epoch = get_current_epoch(state)
    withdrawal_index = state.next_withdrawal_index
    withdrawals: List[Withdrawal] = []

    # [New in Gloas:EIP7732]
    # Get builder withdrawals
    builder_withdrawals, withdrawal_index, processed_builder_withdrawals_count = (
        get_builder_withdrawals(state, withdrawal_index, epoch, withdrawals)
    )
    withdrawals.extend(builder_withdrawals)

    # Get partial withdrawals
    partial_withdrawals, withdrawal_index, processed_partial_withdrawals_count = (
        get_pending_partial_withdrawals(state, withdrawal_index, epoch, withdrawals)
    )
    withdrawals.extend(partial_withdrawals)

    # Get validators sweep withdrawals
    validators_sweep_withdrawals, withdrawal_index, processed_validators_sweep_count = (
        get_validators_sweep_withdrawals(state, withdrawal_index, epoch, withdrawals)
    )
    withdrawals.extend(validators_sweep_withdrawals)

    # [Modified in Gloas:EIP7732]
    return (
        withdrawals,
        processed_builder_withdrawals_count,
        processed_partial_withdrawals_count,
        processed_validators_sweep_count,
    )
```

##### New `update_payload_expected_withdrawals`

```python
def update_payload_expected_withdrawals(
    state: BeaconState, withdrawals: Sequence[Withdrawal]
) -> None:
    state.payload_expected_withdrawals = List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD](withdrawals)
```

##### New `update_builder_pending_withdrawals`

```python
def update_builder_pending_withdrawals(
    state: BeaconState, processed_builder_withdrawals_count: uint64
) -> None:
    deferred_withdrawals = [
        withdrawal
        for withdrawal in state.builder_pending_withdrawals[:processed_builder_withdrawals_count]
        if not is_builder_payment_withdrawable(state, withdrawal)
    ]
    unprocessed_withdrawals = state.builder_pending_withdrawals[
        processed_builder_withdrawals_count:
    ]

    state.builder_pending_withdrawals = deferred_withdrawals + unprocessed_withdrawals
```

##### Modified `process_withdrawals`

*Note*: This is modified to only take the `state` as parameter. Withdrawals are
deterministic given the beacon state, any execution payload that has the
corresponding block as parent beacon block is required to honor these
withdrawals in the execution layer. `process_withdrawals` must be called before
`process_execution_payload_bid` as the latter function affects validator
balances.

```python
def process_withdrawals(
    state: BeaconState,
    # [Modified in Gloas:EIP7732]
    # Removed `payload`
) -> None:
    # [New in Gloas:EIP7732]
    # Return early if the parent block is empty
    if not is_parent_block_full(state):
        return

    # [Modified in Gloas:EIP7732]
    # Get expected withdrawals
    (
        withdrawals,
        processed_builder_withdrawals_count,
        processed_partial_withdrawals_count,
        processed_validators_sweep_count,
    ) = get_expected_withdrawals(state)

    # Apply expected withdrawals
    apply_withdrawals(state, withdrawals)

    # Update withdrawals fields in the state
    update_next_withdrawal_index(state, withdrawals)
    # [New in Gloas:EIP7732]
    update_payload_expected_withdrawals(state, withdrawals)
    # [New in Gloas:EIP7732]
    update_builder_pending_withdrawals(state, processed_builder_withdrawals_count)
    update_pending_partial_withdrawals(state, processed_partial_withdrawals_count)
    update_next_withdrawal_validator_index(state, processed_validators_sweep_count)
```

#### Execution payload bid

##### New `verify_execution_payload_bid_signature`

```python
def verify_execution_payload_bid_signature(
    state: BeaconState, signed_bid: SignedExecutionPayloadBid
) -> bool:
    builder = state.validators[signed_bid.message.builder_index]
    signing_root = compute_signing_root(
        signed_bid.message, get_domain(state, DOMAIN_BEACON_BUILDER)
    )
    return bls.Verify(builder.pubkey, signing_root, signed_bid.signature)
```

##### New `process_execution_payload_bid`

```python
def process_execution_payload_bid(state: BeaconState, block: BeaconBlock) -> None:
    signed_bid = block.body.signed_execution_payload_bid
    bid = signed_bid.message
    builder_index = bid.builder_index
    builder = state.validators[builder_index]

    amount = bid.value
    # For self-builds, amount must be zero regardless of withdrawal credential prefix
    if builder_index == block.proposer_index:
        assert amount == 0
        assert signed_bid.signature == bls.G2_POINT_AT_INFINITY
    else:
        # Non-self builds require builder withdrawal credential
        assert has_builder_withdrawal_credential(builder)
        assert verify_execution_payload_bid_signature(state, signed_bid)

    assert is_active_validator(builder, get_current_epoch(state))
    assert not builder.slashed

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
    assert bid.slot == block.slot
    # Verify that the bid is for the right parent block
    assert bid.parent_block_hash == state.latest_block_hash
    assert bid.parent_block_root == block.parent_root
    assert bid.prev_randao == get_randao_mix(state, get_current_epoch(state))

    # Record the pending payment if there is some payment
    if amount > 0:
        pending_payment = BuilderPendingPayment(
            weight=0,
            withdrawal=BuilderPendingWithdrawal(
                fee_recipient=bid.fee_recipient,
                amount=amount,
                builder_index=builder_index,
                withdrawable_epoch=FAR_FUTURE_EPOCH,
            ),
        )
        state.builder_pending_payments[SLOTS_PER_EPOCH + bid.slot % SLOTS_PER_EPOCH] = (
            pending_payment
        )

    # Cache the signed execution payload bid
    state.latest_execution_payload_bid = bid
```

#### Operations

##### Modified `process_operations`

*Note*: `process_operations` is modified to process PTC attestations and removes
calls to `process_deposit_request`, `process_withdrawal_request`, and
`process_consolidation_request`.

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    assert len(body.deposits) == 0
    if state.deposit_requests_start_index != UNSET_DEPOSIT_REQUESTS_START_INDEX:
        assert state.eth1_data.deposit_count >= state.deposit_requests_start_index

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    # [Modified in Gloas:EIP7732]
    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    # [Modified in Gloas:EIP7732]
    for_ops(body.attestations, process_attestation)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    # [Modified in Gloas:EIP7732]
    # Removed `process_deposit_request`
    # [Modified in Gloas:EIP7732]
    # Removed `process_withdrawal_request`
    # [Modified in Gloas:EIP7732]
    # Removed `process_consolidation_request`
    # [New in Gloas:EIP7732]
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

    # [Modified in Gloas:EIP7732]
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

    # [Modified in Gloas:EIP7732]
    if data.target.epoch == get_current_epoch(state):
        current_epoch_target = True
        epoch_participation = state.current_epoch_participation
        payment = state.builder_pending_payments[SLOTS_PER_EPOCH + data.slot % SLOTS_PER_EPOCH]
    else:
        current_epoch_target = False
        epoch_participation = state.previous_epoch_participation
        payment = state.builder_pending_payments[data.slot % SLOTS_PER_EPOCH]

    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, attestation):
        # [New in Gloas:EIP7732]
        # For same-slot attestations, check if we are setting any new flags.
        # If we are, this validator has not contributed to this slot's quorum yet.
        will_set_new_flag = False

        for flag_index, weight in enumerate(PARTICIPATION_FLAG_WEIGHTS):
            if flag_index in participation_flag_indices and not has_flag(
                epoch_participation[index], flag_index
            ):
                epoch_participation[index] = add_flag(epoch_participation[index], flag_index)
                proposer_reward_numerator += get_base_reward(state, index) * weight
                # [New in Gloas:EIP7732]
                will_set_new_flag = True

        # [New in Gloas:EIP7732]
        # Add weight for same-slot attestations when any new flag is set.
        # This ensures each validator contributes exactly once per slot.
        if (
            will_set_new_flag
            and is_attestation_same_slot(state, data)
            and payment.withdrawal.amount > 0
        ):
            payment.weight += state.validators[index].effective_balance

    # Reward proposer
    proposer_reward_denominator = (
        (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT) * WEIGHT_DENOMINATOR // PROPOSER_WEIGHT
    )
    proposer_reward = Gwei(proposer_reward_numerator // proposer_reward_denominator)
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)

    # [New in Gloas:EIP7732]
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
    data = payload_attestation.data

    # Check that the attestation is for the parent beacon block
    assert data.beacon_block_root == state.latest_block_header.parent_root
    # Check that the attestation is for the previous slot
    assert data.slot + 1 == state.slot
    # Verify signature
    indexed_payload_attestation = get_indexed_payload_attestation(
        state, data.slot, payload_attestation
    )
    assert is_valid_indexed_payload_attestation(state, indexed_payload_attestation)
```

##### Proposer Slashing

###### Modified `process_proposer_slashing`

```python
def process_proposer_slashing(state: BeaconState, proposer_slashing: ProposerSlashing) -> None:
    header_1 = proposer_slashing.signed_header_1.message
    header_2 = proposer_slashing.signed_header_2.message

    # Verify header slots match
    assert header_1.slot == header_2.slot
    # Verify header proposer indices match
    assert header_1.proposer_index == header_2.proposer_index
    # Verify the headers are different
    assert header_1 != header_2
    # Verify the proposer is slashable
    proposer = state.validators[header_1.proposer_index]
    assert is_slashable_validator(proposer, get_current_epoch(state))
    # Verify signatures
    for signed_header in (proposer_slashing.signed_header_1, proposer_slashing.signed_header_2):
        domain = get_domain(
            state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(signed_header.message.slot)
        )
        signing_root = compute_signing_root(signed_header.message, domain)
        assert bls.Verify(proposer.pubkey, signing_root, signed_header.signature)

    # [New in Gloas:EIP7732]
    # Remove the BuilderPendingPayment corresponding to
    # this proposal if it is still in the 2-epoch window.
    slot = header_1.slot
    proposal_epoch = compute_epoch_at_slot(slot)
    if proposal_epoch == get_current_epoch(state):
        payment_index = SLOTS_PER_EPOCH + slot % SLOTS_PER_EPOCH
        state.builder_pending_payments[payment_index] = BuilderPendingPayment()
    elif proposal_epoch == get_previous_epoch(state):
        payment_index = slot % SLOTS_PER_EPOCH
        state.builder_pending_payments[payment_index] = BuilderPendingPayment()

    slash_validator(state, header_1.proposer_index)
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
