# Gloas -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
- [Constants](#constants)
  - [Index flags](#index-flags)
  - [Domains](#domains)
  - [Misc](#misc)
  - [Withdrawal prefixes](#withdrawal-prefixes)
- [Preset](#preset)
  - [Misc](#misc-1)
  - [Max operations per block](#max-operations-per-block)
  - [State list lengths](#state-list-lengths)
  - [Withdrawals processing](#withdrawals-processing)
- [Configuration](#configuration)
  - [Validator cycle](#validator-cycle)
  - [Time parameters](#time-parameters)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`Builder`](#builder)
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
    - [`ExecutionPayload`](#executionpayload)
- [Dataclasses](#dataclasses)
  - [Modified dataclasses](#modified-dataclasses)
    - [`ExpectedWithdrawals`](#expectedwithdrawals)
- [Helpers](#helpers)
  - [Predicates](#predicates)
    - [New `is_builder_index`](#new-is_builder_index)
    - [New `is_active_builder`](#new-is_active_builder)
    - [New `is_builder_withdrawal_credential`](#new-is_builder_withdrawal_credential)
    - [New `is_attestation_same_slot`](#new-is_attestation_same_slot)
    - [New `is_valid_indexed_payload_attestation`](#new-is_valid_indexed_payload_attestation)
    - [New `is_pending_validator`](#new-is_pending_validator)
  - [Misc](#misc-2)
    - [New `convert_builder_index_to_validator_index`](#new-convert_builder_index_to_validator_index)
    - [New `convert_validator_index_to_builder_index`](#new-convert_validator_index_to_builder_index)
    - [New `get_pending_balance_to_withdraw_for_builder`](#new-get_pending_balance_to_withdraw_for_builder)
    - [New `can_builder_cover_bid`](#new-can_builder_cover_bid)
    - [New `compute_balance_weighted_selection`](#new-compute_balance_weighted_selection)
    - [Modified `compute_proposer_indices`](#modified-compute_proposer_indices)
    - [New `compute_ptc`](#new-compute_ptc)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Modified `get_next_sync_committee_indices`](#modified-get_next_sync_committee_indices)
    - [Modified `get_attestation_participation_flag_indices`](#modified-get_attestation_participation_flag_indices)
    - [New `get_ptc`](#new-get_ptc)
    - [New `get_indexed_payload_attestation`](#new-get_indexed_payload_attestation)
    - [New `get_builder_payment_quorum_threshold`](#new-get_builder_payment_quorum_threshold)
    - [New `get_activation_churn_limit`](#new-get_activation_churn_limit)
    - [New `get_exit_churn_limit`](#new-get_exit_churn_limit)
    - [Modified `get_consolidation_churn_limit`](#modified-get_consolidation_churn_limit)
    - [Modified `compute_exit_epoch_and_update_churn`](#modified-compute_exit_epoch_and_update_churn)
  - [Beacon state mutators](#beacon-state-mutators)
    - [New `initiate_builder_exit`](#new-initiate_builder_exit)
    - [New `settle_builder_payment`](#new-settle_builder_payment)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Modified `process_slot`](#modified-process_slot)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [Modified `process_pending_deposits`](#modified-process_pending_deposits)
    - [New `process_builder_pending_payments`](#new-process_builder_pending_payments)
    - [New `process_ptc_window`](#new-process_ptc_window)
  - [Block processing](#block-processing)
    - [Parent execution payload](#parent-execution-payload)
      - [New `apply_parent_execution_payload`](#new-apply_parent_execution_payload)
      - [New `process_parent_execution_payload`](#new-process_parent_execution_payload)
    - [Withdrawals](#withdrawals)
      - [New `get_builder_withdrawals`](#new-get_builder_withdrawals)
      - [New `get_builders_sweep_withdrawals`](#new-get_builders_sweep_withdrawals)
      - [Modified `get_expected_withdrawals`](#modified-get_expected_withdrawals)
      - [Modified `apply_withdrawals`](#modified-apply_withdrawals)
      - [New `update_payload_expected_withdrawals`](#new-update_payload_expected_withdrawals)
      - [New `update_builder_pending_withdrawals`](#new-update_builder_pending_withdrawals)
      - [New `update_next_withdrawal_builder_index`](#new-update_next_withdrawal_builder_index)
      - [Modified `process_withdrawals`](#modified-process_withdrawals)
    - [Execution payload](#execution-payload)
      - [Removed `process_execution_payload`](#removed-process_execution_payload)
    - [Execution payload bid](#execution-payload-bid)
      - [New `verify_execution_payload_bid_signature`](#new-verify_execution_payload_bid_signature)
      - [New `process_execution_payload_bid`](#new-process_execution_payload_bid)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [Deposit requests](#deposit-requests)
        - [New `get_index_for_new_builder`](#new-get_index_for_new_builder)
        - [New `add_builder_to_registry`](#new-add_builder_to_registry)
        - [New `apply_deposit_for_builder`](#new-apply_deposit_for_builder)
        - [Modified `process_deposit_request`](#modified-process_deposit_request)
      - [Voluntary exits](#voluntary-exits)
        - [Modified `process_voluntary_exit`](#modified-process_voluntary_exit)
      - [Attestations](#attestations)
        - [Modified `process_attestation`](#modified-process_attestation)
      - [Payload attestations](#payload-attestations)
        - [New `process_payload_attestation`](#new-process_payload_attestation)
      - [Proposer slashing](#proposer-slashing)
        - [Modified `process_proposer_slashing`](#modified-process_proposer_slashing)

<!-- mdformat-toc end -->

## Introduction

Gloas is a consensus-layer upgrade containing a number of features. Including:

- [EIP-7732](https://eips.ethereum.org/EIPS/eip-7732): Enshrined
  Proposer-Builder Separation
- [EIP-7843](https://eips.ethereum.org/EIPS/eip-7843): SLOTNUM opcode
- [EIP-8061](https://eips.ethereum.org/EIPS/eip-8061): Increase exit and
  consolidation churn

## Types

| Name              | SSZ equivalent                        | Description                   |
| ----------------- | ------------------------------------- | ----------------------------- |
| `BuilderIndex`    | `uint64`                              | Builder registry index        |
| `BlockAccessList` | `ByteList[MAX_BYTES_PER_TRANSACTION]` | RLP encoded block access list |

## Constants

### Index flags

| Name                 | Value           | Description                                                                                |
| -------------------- | --------------- | ------------------------------------------------------------------------------------------ |
| `BUILDER_INDEX_FLAG` | `uint64(2**40)` | Bitwise flag which indicates that a `ValidatorIndex` should be treated as a `BuilderIndex` |

### Domains

| Name                          | Value                      |
| ----------------------------- | -------------------------- |
| `DOMAIN_BEACON_BUILDER`       | `DomainType('0x0B000000')` |
| `DOMAIN_PTC_ATTESTER`         | `DomainType('0x0C000000')` |
| `DOMAIN_PROPOSER_PREFERENCES` | `DomainType('0x0D000000')` |

### Misc

| Name                                    | Value                      | Description                                          |
| --------------------------------------- | -------------------------- | ---------------------------------------------------- |
| `BUILDER_INDEX_SELF_BUILD`              | `BuilderIndex(UINT64_MAX)` | Value which indicates the proposer built the payload |
| `BUILDER_PAYMENT_THRESHOLD_NUMERATOR`   | `uint64(6)`                |                                                      |
| `BUILDER_PAYMENT_THRESHOLD_DENOMINATOR` | `uint64(10)`               |                                                      |

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

| Name                                | Value                                 | Unit                        |
| ----------------------------------- | ------------------------------------- | --------------------------- |
| `BUILDER_REGISTRY_LIMIT`            | `uint64(2**40)` (= 1,099,511,627,776) | Builders                    |
| `BUILDER_PENDING_WITHDRAWALS_LIMIT` | `uint64(2**20)` (= 1,048,576)         | Builder pending withdrawals |

### Withdrawals processing

| Name                                 | Value              |
| ------------------------------------ | ------------------ |
| `MAX_BUILDERS_PER_WITHDRAWALS_SWEEP` | `2**14` (= 16,384) |

## Configuration

### Validator cycle

| Name                                         | Value                                    |
| -------------------------------------------- | ---------------------------------------- |
| `CHURN_LIMIT_QUOTIENT_GLOAS`                 | `uint64(2**15)` (= 32,768)               |
| `CONSOLIDATION_CHURN_LIMIT_QUOTIENT`         | `uint64(2**16)` (= 65,536)               |
| `MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS` | `Gwei(2**8 * 10**9)` (= 256,000,000,000) |

### Time parameters

| Name                                | Value                     |  Unit  |
| ----------------------------------- | ------------------------- | :----: |
| `MIN_BUILDER_WITHDRAWABILITY_DELAY` | `uint64(2**13)` (= 8,192) | epochs |

## Containers

### New containers

#### `Builder`

```python
class Builder(Container):
    pubkey: BLSPubkey
    version: uint8
    execution_address: ExecutionAddress
    balance: Gwei
    deposit_epoch: Epoch
    withdrawable_epoch: Epoch
```

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
    builder_index: BuilderIndex
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
    builder_index: BuilderIndex
    slot: Slot
    value: Gwei
    execution_payment: Gwei
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    execution_requests_root: Root
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
    builder_index: BuilderIndex
    beacon_block_root: Root
    parent_beacon_block_root: Root
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
    # [New in Gloas:EIP7732]
    parent_execution_requests: ExecutionRequests
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
    latest_block_hash: Hash32
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
    builders: List[Builder, BUILDER_REGISTRY_LIMIT]
    # [New in Gloas:EIP7732]
    next_withdrawal_builder_index: BuilderIndex
    # [New in Gloas:EIP7732]
    execution_payload_availability: Bitvector[SLOTS_PER_HISTORICAL_ROOT]
    # [New in Gloas:EIP7732]
    builder_pending_payments: Vector[BuilderPendingPayment, 2 * SLOTS_PER_EPOCH]
    # [New in Gloas:EIP7732]
    builder_pending_withdrawals: List[BuilderPendingWithdrawal, BUILDER_PENDING_WITHDRAWALS_LIMIT]
    # [New in Gloas:EIP7732]
    latest_execution_payload_bid: ExecutionPayloadBid
    # [New in Gloas:EIP7732]
    payload_expected_withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
    # [New in Gloas:EIP7732]
    ptc_window: Vector[Vector[ValidatorIndex, PTC_SIZE], (2 + MIN_SEED_LOOKAHEAD) * SLOTS_PER_EPOCH]
```

#### `ExecutionPayload`

```python
class ExecutionPayload(Container):
    parent_hash: Hash32
    fee_recipient: ExecutionAddress
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    block_hash: Hash32
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
    blob_gas_used: uint64
    excess_blob_gas: uint64
    # [New in Gloas:EIP7928]
    block_access_list: BlockAccessList
    # [New in Gloas:EIP7843]
    slot_number: uint64
```

## Dataclasses

### Modified dataclasses

#### `ExpectedWithdrawals`

```python
@dataclass
class ExpectedWithdrawals(object):
    withdrawals: Sequence[Withdrawal]
    # [New in Gloas:EIP7732]
    processed_builder_withdrawals_count: uint64
    processed_partial_withdrawals_count: uint64
    # [New in Gloas:EIP7732]
    processed_builders_sweep_count: uint64
    processed_sweep_withdrawals_count: uint64
```

## Helpers

### Predicates

#### New `is_builder_index`

```python
def is_builder_index(validator_index: ValidatorIndex) -> bool:
    return (validator_index & BUILDER_INDEX_FLAG) != 0
```

#### New `is_active_builder`

```python
def is_active_builder(state: BeaconState, builder_index: BuilderIndex) -> bool:
    """
    Check if the builder at ``builder_index`` is active for the given ``state``.
    """
    builder = state.builders[builder_index]
    return (
        # Placement in builder list is finalized
        builder.deposit_epoch < state.finalized_checkpoint.epoch
        # Has not initiated exit
        and builder.withdrawable_epoch == FAR_FUTURE_EPOCH
    )
```

#### New `is_builder_withdrawal_credential`

```python
def is_builder_withdrawal_credential(withdrawal_credentials: Bytes32) -> bool:
    return withdrawal_credentials[:1] == BUILDER_WITHDRAWAL_PREFIX
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
    state: BeaconState, attestation: IndexedPayloadAttestation
) -> bool:
    """
    Check if ``attestation`` is non-empty, has sorted indices, and has
    a valid aggregate signature.
    """
    # Verify indices are non-empty and sorted
    indices = attestation.attesting_indices
    if len(indices) == 0 or not indices == sorted(indices):
        return False

    # Verify aggregate signature
    pubkeys = [state.validators[i].pubkey for i in indices]
    domain = get_domain(state, DOMAIN_PTC_ATTESTER, compute_epoch_at_slot(attestation.data.slot))
    signing_root = compute_signing_root(attestation.data, domain)
    return bls.FastAggregateVerify(pubkeys, signing_root, attestation.signature)
```

#### New `is_pending_validator`

*Note*: This function naively revalidates deposit signatures on every call.
Implementations SHOULD cache verification results to avoid repeated work.

```python
def is_pending_validator(pending_deposits: Sequence[PendingDeposit], pubkey: BLSPubkey) -> bool:
    """
    Check if a pending deposit with a valid signature is in the queue for the given pubkey.
    """
    for pending_deposit in pending_deposits:
        if pending_deposit.pubkey != pubkey:
            continue
        if is_valid_deposit_signature(
            pending_deposit.pubkey,
            pending_deposit.withdrawal_credentials,
            pending_deposit.amount,
            pending_deposit.signature,
        ):
            return True
    return False
```

### Misc

#### New `convert_builder_index_to_validator_index`

```python
def convert_builder_index_to_validator_index(builder_index: BuilderIndex) -> ValidatorIndex:
    return ValidatorIndex(builder_index | BUILDER_INDEX_FLAG)
```

#### New `convert_validator_index_to_builder_index`

```python
def convert_validator_index_to_builder_index(validator_index: ValidatorIndex) -> BuilderIndex:
    return BuilderIndex(validator_index & ~BUILDER_INDEX_FLAG)
```

#### New `get_pending_balance_to_withdraw_for_builder`

```python
def get_pending_balance_to_withdraw_for_builder(
    state: BeaconState, builder_index: BuilderIndex
) -> Gwei:
    return sum(
        withdrawal.amount
        for withdrawal in state.builder_pending_withdrawals
        if withdrawal.builder_index == builder_index
    ) + sum(
        payment.withdrawal.amount
        for payment in state.builder_pending_payments
        if payment.withdrawal.builder_index == builder_index
    )
```

#### New `can_builder_cover_bid`

```python
def can_builder_cover_bid(
    state: BeaconState, builder_index: BuilderIndex, bid_amount: Gwei
) -> bool:
    builder_balance = state.builders[builder_index].balance
    pending_withdrawals_amount = get_pending_balance_to_withdraw_for_builder(state, builder_index)
    min_balance = MIN_DEPOSIT_AMOUNT + pending_withdrawals_amount
    if builder_balance < min_balance:
        return False
    return builder_balance - min_balance >= bid_amount
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
    ``indices`` is traversed in order. The returned list can contain duplicates.
    """
    MAX_RANDOM_VALUE = 2**16 - 1
    total = uint64(len(indices))
    assert total > 0
    effective_balances = [state.validators[index].effective_balance for index in indices]
    selected: List[ValidatorIndex] = []
    i = uint64(0)
    while len(selected) < size:
        offset = i % 16 * 2
        if offset == 0:
            random_bytes = hash(seed + uint_to_bytes(i // 16))
        next_index = i % total
        if shuffle_indices:
            next_index = compute_shuffled_index(next_index, total, seed)
        weight = effective_balances[next_index] * MAX_RANDOM_VALUE
        random_value = bytes_to_uint64(random_bytes[offset : offset + 2])
        threshold = MAX_EFFECTIVE_BALANCE_ELECTRA * random_value
        if weight >= threshold:
            selected.append(indices[next_index])
        i += 1
    return selected
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

#### New `compute_ptc`

```python
def compute_ptc(state: BeaconState, slot: Slot) -> Vector[ValidatorIndex, PTC_SIZE]:
    """
    Get the payload timeliness committee, with possible duplicates, for the given ``slot``.
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

### Beacon state accessors

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

*Note*: `get_ptc` uses the cached `ptc_window` for lookups.

```python
def get_ptc(state: BeaconState, slot: Slot) -> Vector[ValidatorIndex, PTC_SIZE]:
    """
    Get the payload timeliness committee for the given ``slot``.
    """
    epoch = compute_epoch_at_slot(slot)
    state_epoch = get_current_epoch(state)
    if epoch < state_epoch:
        assert epoch + 1 == state_epoch
        return state.ptc_window[slot % SLOTS_PER_EPOCH]
    assert epoch <= state_epoch + MIN_SEED_LOOKAHEAD
    offset = (epoch - state_epoch + 1) * SLOTS_PER_EPOCH
    return state.ptc_window[offset + slot % SLOTS_PER_EPOCH]
```

#### New `get_indexed_payload_attestation`

```python
def get_indexed_payload_attestation(
    state: BeaconState, payload_attestation: PayloadAttestation
) -> IndexedPayloadAttestation:
    """
    Return the indexed payload attestation corresponding to ``payload_attestation``.
    """
    slot = payload_attestation.data.slot
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

#### New `get_activation_churn_limit`

```python
def get_activation_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit for activations, rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = max(
        MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        get_total_active_balance(state) // CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    churn = churn - churn % EFFECTIVE_BALANCE_INCREMENT
    return min(MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS, churn)
```

#### New `get_exit_churn_limit`

```python
def get_exit_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit for exits, rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = max(
        MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        get_total_active_balance(state) // CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    return churn - churn % EFFECTIVE_BALANCE_INCREMENT
```

#### Modified `get_consolidation_churn_limit`

*Note*: Consolidation churn is now independently derived from the total active
balance using `CONSOLIDATION_CHURN_LIMIT_QUOTIENT`.

```python
def get_consolidation_churn_limit(state: BeaconState) -> Gwei:
    """
    Per-epoch churn limit reserved for consolidations (EIP-7521).
    Derived from total active balance and rounded to
    ``EFFECTIVE_BALANCE_INCREMENT``.
    """
    churn = get_total_active_balance(state) // CONSOLIDATION_CHURN_LIMIT_QUOTIENT
    return churn - churn % EFFECTIVE_BALANCE_INCREMENT
```

#### Modified `compute_exit_epoch_and_update_churn`

*Note*: Exit processing now uses the uncapped exit churn, while deposit
processing remains capped by `get_activation_churn_limit`.

```python
def compute_exit_epoch_and_update_churn(state: BeaconState, exit_balance: Gwei) -> Epoch:
    earliest_exit_epoch = max(
        state.earliest_exit_epoch, compute_activation_exit_epoch(get_current_epoch(state))
    )
    # [Modified in Gloas:EIP8061]
    per_epoch_churn = get_exit_churn_limit(state)
    # New epoch for exits.
    if state.earliest_exit_epoch < earliest_exit_epoch:
        exit_balance_to_consume = per_epoch_churn
    else:
        exit_balance_to_consume = state.exit_balance_to_consume

    # Exit doesn't fit in the current earliest epoch.
    if exit_balance > exit_balance_to_consume:
        balance_to_process = exit_balance - exit_balance_to_consume
        additional_epochs = (balance_to_process - 1) // per_epoch_churn + 1
        earliest_exit_epoch += additional_epochs
        exit_balance_to_consume += additional_epochs * per_epoch_churn

    # Consume the balance and update state variables.
    state.exit_balance_to_consume = exit_balance_to_consume - exit_balance
    state.earliest_exit_epoch = earliest_exit_epoch

    return state.earliest_exit_epoch
```

### Beacon state mutators

#### New `initiate_builder_exit`

```python
def initiate_builder_exit(state: BeaconState, builder_index: BuilderIndex) -> None:
    """
    Initiate the exit of the builder with index ``index``.
    """
    # Set builder exit epoch
    builder = state.builders[builder_index]
    builder.withdrawable_epoch = get_current_epoch(state) + MIN_BUILDER_WITHDRAWABILITY_DELAY
```

#### New `settle_builder_payment`

```python
def settle_builder_payment(state: BeaconState, payment_index: uint64) -> None:
    assert payment_index < len(state.builder_pending_payments)
    payment = state.builder_pending_payments[payment_index]
    if payment.withdrawal.amount > 0:
        state.builder_pending_withdrawals.append(payment.withdrawal)
    state.builder_pending_payments[payment_index] = BuilderPendingPayment()
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

The validity of a signed execution payload envelope `signed_envelope` against a
pre-state `state` is checked by
`verify_execution_payload_envelope(state, signed_envelope, execution_engine)`.
Payload processing is deferred to the next beacon block via
`process_parent_execution_payload`. Payloads that trigger an unhandled exception
(e.g. a failed `assert` or an out-of-range list access) are considered invalid.
Payloads that cause a `uint64` overflow or underflow are also considered
invalid.

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

*Note*: The function `process_epoch` is modified in Gloas to call the new
helpers `process_builder_pending_payments` and `process_ptc_window`.

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    # [Modified in Gloas:EIP8061]
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
    # [New in Gloas:EIP7732]
    process_ptc_window(state)
```

#### Modified `process_pending_deposits`

```python
def process_pending_deposits(state: BeaconState) -> None:
    next_epoch = Epoch(get_current_epoch(state) + 1)
    # [Modified in Gloas:EIP8061]
    # Deposits still consume the activation-only churn budget in Gloas.
    available_for_processing = state.deposit_balance_to_consume + get_activation_churn_limit(state)
    processed_amount = 0
    next_deposit_index = 0
    deposits_to_postpone = []
    is_churn_limit_reached = False
    finalized_slot = compute_start_slot_at_epoch(state.finalized_checkpoint.epoch)

    for deposit in state.pending_deposits:
        # Do not process deposit requests if Eth1 bridge deposits are not yet applied.
        if (
            # Is deposit request
            deposit.slot > GENESIS_SLOT
            and
            # There are pending Eth1 bridge deposits
            state.eth1_deposit_index < state.deposit_requests_start_index
        ):
            break

        # Check if deposit has been finalized, otherwise, stop processing.
        if deposit.slot > finalized_slot:
            break

        # Check if number of processed deposits has not reached the limit, otherwise, stop processing.
        if next_deposit_index >= MAX_PENDING_DEPOSITS_PER_EPOCH:
            break

        # Read validator state
        is_validator_exited = False
        is_validator_withdrawn = False
        validator_pubkeys = [v.pubkey for v in state.validators]
        if deposit.pubkey in validator_pubkeys:
            validator = state.validators[ValidatorIndex(validator_pubkeys.index(deposit.pubkey))]
            is_validator_exited = validator.exit_epoch < FAR_FUTURE_EPOCH
            is_validator_withdrawn = validator.withdrawable_epoch < next_epoch

        if is_validator_withdrawn:
            # Deposited balance will never become active. Increase balance but do not consume churn
            apply_pending_deposit(state, deposit)
        elif is_validator_exited:
            # Validator is exiting, postpone the deposit until after withdrawable epoch
            deposits_to_postpone.append(deposit)
        else:
            # Check if deposit fits in the churn, otherwise, do no more deposit processing in this epoch.
            is_churn_limit_reached = processed_amount + deposit.amount > available_for_processing
            if is_churn_limit_reached:
                break

            # Consume churn and apply deposit.
            processed_amount += deposit.amount
            apply_pending_deposit(state, deposit)

        # Regardless of how the deposit was handled, we move on in the queue.
        next_deposit_index += 1

    state.pending_deposits = state.pending_deposits[next_deposit_index:] + deposits_to_postpone

    # Accumulate churn only if the churn limit has been hit.
    if is_churn_limit_reached:
        state.deposit_balance_to_consume = available_for_processing - processed_amount
    else:
        state.deposit_balance_to_consume = Gwei(0)
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
            state.builder_pending_withdrawals.append(payment.withdrawal)

    old_payments = state.builder_pending_payments[SLOTS_PER_EPOCH:]
    new_payments = [BuilderPendingPayment() for _ in range(SLOTS_PER_EPOCH)]
    state.builder_pending_payments = old_payments + new_payments
```

#### New `process_ptc_window`

```python
def process_ptc_window(state: BeaconState) -> None:
    """
    Update the cached PTC window.
    """
    # Shift all epochs forward by one
    state.ptc_window[: len(state.ptc_window) - SLOTS_PER_EPOCH] = state.ptc_window[SLOTS_PER_EPOCH:]
    # Fill in the last epoch
    next_epoch = Epoch(get_current_epoch(state) + MIN_SEED_LOOKAHEAD + 1)
    start_slot = compute_start_slot_at_epoch(next_epoch)
    state.ptc_window[len(state.ptc_window) - SLOTS_PER_EPOCH :] = [
        compute_ptc(state, Slot(slot)) for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH)
    ]
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    # [New in Gloas:EIP7732]
    process_parent_execution_payload(state, block)
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

#### Parent execution payload

##### New `apply_parent_execution_payload`

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

    # Process execution requests from parent's payload. The execution
    # requests are processed at state.slot (child's slot), not the parent's slot.
    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(requests.deposits, process_deposit_request)
    for_ops(requests.withdrawals, process_withdrawal_request)
    for_ops(requests.consolidations, process_consolidation_request)

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

##### New `process_parent_execution_payload`

*Note*: This function validates and processes the parent's execution payload.
`process_parent_execution_payload` must be called before
`process_execution_payload_bid` (which overwrites
`state.latest_execution_payload_bid`).

```python
def process_parent_execution_payload(state: BeaconState, block: BeaconBlock) -> None:
    bid = block.body.signed_execution_payload_bid.message
    parent_bid = state.latest_execution_payload_bid
    requests = block.body.parent_execution_requests

    if bid.parent_block_hash != parent_bid.block_hash:
        # Parent was EMPTY -- no execution requests expected
        assert requests == ExecutionRequests()
        return

    # Parent was FULL -- verify the bid commitment and apply the payload
    assert hash_tree_root(requests) == parent_bid.execution_requests_root
    apply_parent_execution_payload(state, requests)
```

#### Withdrawals

##### New `get_builder_withdrawals`

```python
def get_builder_withdrawals(
    state: BeaconState,
    withdrawal_index: WithdrawalIndex,
    prior_withdrawals: Sequence[Withdrawal],
) -> Tuple[Sequence[Withdrawal], WithdrawalIndex, uint64]:
    withdrawals_limit = MAX_WITHDRAWALS_PER_PAYLOAD - 1
    assert len(prior_withdrawals) <= withdrawals_limit

    processed_count: uint64 = 0
    withdrawals: List[Withdrawal] = []
    for withdrawal in state.builder_pending_withdrawals:
        all_withdrawals = prior_withdrawals + withdrawals
        has_reached_limit = len(all_withdrawals) >= withdrawals_limit
        if has_reached_limit:
            break

        builder_index = withdrawal.builder_index
        withdrawals.append(
            Withdrawal(
                index=withdrawal_index,
                validator_index=convert_builder_index_to_validator_index(builder_index),
                address=withdrawal.fee_recipient,
                amount=withdrawal.amount,
            )
        )
        withdrawal_index += WithdrawalIndex(1)
        processed_count += 1

    return withdrawals, withdrawal_index, processed_count
```

##### New `get_builders_sweep_withdrawals`

```python
def get_builders_sweep_withdrawals(
    state: BeaconState,
    withdrawal_index: WithdrawalIndex,
    prior_withdrawals: Sequence[Withdrawal],
) -> Tuple[Sequence[Withdrawal], WithdrawalIndex, uint64]:
    epoch = get_current_epoch(state)
    builders_limit = min(len(state.builders), MAX_BUILDERS_PER_WITHDRAWALS_SWEEP)
    withdrawals_limit = MAX_WITHDRAWALS_PER_PAYLOAD - 1
    assert len(prior_withdrawals) <= withdrawals_limit

    processed_count: uint64 = 0
    withdrawals: List[Withdrawal] = []
    builder_index = state.next_withdrawal_builder_index
    for _ in range(builders_limit):
        all_withdrawals = prior_withdrawals + withdrawals
        has_reached_limit = len(all_withdrawals) >= withdrawals_limit
        if has_reached_limit:
            break

        builder = state.builders[builder_index]
        if builder.withdrawable_epoch <= epoch and builder.balance > 0:
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=convert_builder_index_to_validator_index(builder_index),
                    address=builder.execution_address,
                    amount=builder.balance,
                )
            )
            withdrawal_index += WithdrawalIndex(1)

        builder_index = BuilderIndex((builder_index + 1) % len(state.builders))
        processed_count += 1

    return withdrawals, withdrawal_index, processed_count
```

##### Modified `get_expected_withdrawals`

```python
def get_expected_withdrawals(state: BeaconState) -> ExpectedWithdrawals:
    withdrawal_index = state.next_withdrawal_index
    withdrawals: List[Withdrawal] = []

    # [New in Gloas:EIP7732]
    # Get builder withdrawals
    builder_withdrawals, withdrawal_index, processed_builder_withdrawals_count = (
        get_builder_withdrawals(state, withdrawal_index, withdrawals)
    )
    withdrawals.extend(builder_withdrawals)

    # Get partial withdrawals
    partial_withdrawals, withdrawal_index, processed_partial_withdrawals_count = (
        get_pending_partial_withdrawals(state, withdrawal_index, withdrawals)
    )
    withdrawals.extend(partial_withdrawals)

    # [New in Gloas:EIP7732]
    # Get builders sweep withdrawals
    builders_sweep_withdrawals, withdrawal_index, processed_builders_sweep_count = (
        get_builders_sweep_withdrawals(state, withdrawal_index, withdrawals)
    )
    withdrawals.extend(builders_sweep_withdrawals)

    # Get validators sweep withdrawals
    validators_sweep_withdrawals, withdrawal_index, processed_validators_sweep_count = (
        get_validators_sweep_withdrawals(state, withdrawal_index, withdrawals)
    )
    withdrawals.extend(validators_sweep_withdrawals)

    return ExpectedWithdrawals(
        withdrawals,
        # [New in Gloas:EIP7732]
        processed_builder_withdrawals_count,
        processed_partial_withdrawals_count,
        # [New in Gloas:EIP7732]
        processed_builders_sweep_count,
        processed_validators_sweep_count,
    )
```

##### Modified `apply_withdrawals`

```python
def apply_withdrawals(state: BeaconState, withdrawals: Sequence[Withdrawal]) -> None:
    for withdrawal in withdrawals:
        # [Modified in Gloas:EIP7732]
        if is_builder_index(withdrawal.validator_index):
            builder_index = convert_validator_index_to_builder_index(withdrawal.validator_index)
            builder_balance = state.builders[builder_index].balance
            state.builders[builder_index].balance -= min(withdrawal.amount, builder_balance)
        else:
            decrease_balance(state, withdrawal.validator_index, withdrawal.amount)
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
    state.builder_pending_withdrawals = state.builder_pending_withdrawals[
        processed_builder_withdrawals_count:
    ]
```

##### New `update_next_withdrawal_builder_index`

```python
def update_next_withdrawal_builder_index(
    state: BeaconState, processed_builders_sweep_count: uint64
) -> None:
    if len(state.builders) > 0:
        # Update the next builder index to start the next withdrawal sweep
        next_index = state.next_withdrawal_builder_index + processed_builders_sweep_count
        next_builder_index = BuilderIndex(next_index % len(state.builders))
        state.next_withdrawal_builder_index = next_builder_index
```

##### Modified `process_withdrawals`

*Note*: This is modified to only take the `state` as parameter. Withdrawals are
deterministic given the beacon state, any execution payload that has the
corresponding block as parent beacon block is required to honor these
withdrawals in the execution layer. `process_withdrawals` must be called after
`process_parent_execution_payload` (which updates `state.latest_block_hash`) and
before `process_execution_payload_bid` as the latter function affects validator
balances.

*Note*: Unlike deposits (which are applied at the child's slot via
`apply_parent_execution_payload`), withdrawal balance deductions are applied
immediately via `apply_withdrawals`. Deferring the deduction to the child's slot
would break the total supply invariant: state transitions between the commitment
slot and the deduction slot (e.g., `process_pending_consolidations` at an epoch
boundary) can reduce a validator's balance below the committed withdrawal
amount, causing `decrease_balance` to saturate at zero. Since the execution
layer mints the full committed amount regardless, any CL-side saturation creates
a net supply inflation. As a consequence, `state.balances` reflects the
withdrawal deduction before the corresponding execution payload is confirmed,
creating a transient asymmetry with the EL state at `state.latest_block_hash`.
Off-chain consumers that require CL/EL balance consistency can reconstruct
pre-deduction balances by adding back `state.payload_expected_withdrawals`.

```python
def process_withdrawals(
    state: BeaconState,
    # [Modified in Gloas:EIP7732]
    # Removed `payload`
) -> None:
    # [New in Gloas:EIP7732]
    # Return early if the parent block is empty
    if state.latest_block_hash != state.latest_execution_payload_bid.block_hash:
        return

    # Get expected withdrawals
    expected = get_expected_withdrawals(state)

    # Apply expected withdrawals
    apply_withdrawals(state, expected.withdrawals)

    # Update withdrawals fields in the state
    update_next_withdrawal_index(state, expected.withdrawals)
    # [New in Gloas:EIP7732]
    update_payload_expected_withdrawals(state, expected.withdrawals)
    # [New in Gloas:EIP7732]
    update_builder_pending_withdrawals(state, expected.processed_builder_withdrawals_count)
    update_pending_partial_withdrawals(state, expected.processed_partial_withdrawals_count)
    # [New in Gloas:EIP7732]
    update_next_withdrawal_builder_index(state, expected.processed_builders_sweep_count)
    update_next_withdrawal_validator_index(state, expected.withdrawals)
```

#### Execution payload

##### Removed `process_execution_payload`

`process_execution_payload` has been replaced by
`verify_execution_payload_envelope`, a pure verification helper called from
`on_execution_payload_envelope`. Payload processing is deferred to the next
beacon block via `process_parent_execution_payload`.

#### Execution payload bid

##### New `verify_execution_payload_bid_signature`

```python
def verify_execution_payload_bid_signature(
    state: BeaconState, signed_bid: SignedExecutionPayloadBid
) -> bool:
    builder = state.builders[signed_bid.message.builder_index]
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
    amount = bid.value

    # For self-builds, amount must be zero regardless of withdrawal credential prefix
    if builder_index == BUILDER_INDEX_SELF_BUILD:
        assert amount == 0
        assert signed_bid.signature == bls.G2_POINT_AT_INFINITY
    else:
        # Verify that the builder is active
        assert is_active_builder(state, builder_index)
        # Verify that the builder has funds to cover the bid
        assert can_builder_cover_bid(state, builder_index, amount)
        # Verify that the bid signature is valid
        assert verify_execution_payload_bid_signature(state, signed_bid)

    # Verify commitments are under limit
    assert (
        len(bid.blob_kzg_commitments)
        <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
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
    # Disable former deposit mechanism once all prior deposits are processed
    eth1_deposit_index_limit = min(
        state.eth1_data.deposit_count, state.deposit_requests_start_index
    )
    if state.eth1_deposit_index < eth1_deposit_index_limit:
        assert len(body.deposits) == min(
            MAX_DEPOSITS, eth1_deposit_index_limit - state.eth1_deposit_index
        )
    else:
        assert len(body.deposits) == 0

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    # [Modified in Gloas:EIP7732]
    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    # [Modified in Gloas:EIP7732]
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    # [Modified in Gloas:EIP7732]
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

##### Deposit requests

###### New `get_index_for_new_builder`

```python
def get_index_for_new_builder(state: BeaconState) -> BuilderIndex:
    for index, builder in enumerate(state.builders):
        if builder.withdrawable_epoch <= get_current_epoch(state) and builder.balance == 0:
            return BuilderIndex(index)
    return BuilderIndex(len(state.builders))
```

###### New `add_builder_to_registry`

```python
def add_builder_to_registry(
    state: BeaconState,
    pubkey: BLSPubkey,
    withdrawal_credentials: Bytes32,
    amount: uint64,
    slot: Slot,
) -> None:
    set_or_append_list(
        state.builders,
        get_index_for_new_builder(state),
        Builder(
            pubkey=pubkey,
            version=uint8(withdrawal_credentials[0]),
            execution_address=ExecutionAddress(withdrawal_credentials[12:]),
            balance=amount,
            deposit_epoch=compute_epoch_at_slot(slot),
            withdrawable_epoch=FAR_FUTURE_EPOCH,
        ),
    )
```

###### New `apply_deposit_for_builder`

*Note*: Builder indices are reusable. When a builder exits, its index may later
be reassigned to a different builder with a new public key. Any deposit sent to
an exited builder is refunded to the builder’s execution address. Exited
builders cannot be reactivated, although a newly registered builder’s public key
may have previously appeared in the builder set. Implementations that rely on
caching should account for this behavior.

```python
def apply_deposit_for_builder(
    state: BeaconState,
    pubkey: BLSPubkey,
    withdrawal_credentials: Bytes32,
    amount: uint64,
    signature: BLSSignature,
    slot: Slot,
) -> None:
    builder_pubkeys = [b.pubkey for b in state.builders]
    if pubkey not in builder_pubkeys:
        # Verify the deposit signature (proof of possession) which is not checked by the deposit contract
        if is_valid_deposit_signature(pubkey, withdrawal_credentials, amount, signature):
            add_builder_to_registry(state, pubkey, withdrawal_credentials, amount, slot)
    else:
        # Increase balance by deposit amount
        builder_index = builder_pubkeys.index(pubkey)
        state.builders[builder_index].balance += amount
```

###### Modified `process_deposit_request`

```python
def process_deposit_request(state: BeaconState, deposit_request: DepositRequest) -> None:
    # [New in Gloas:EIP7732]
    builder_pubkeys = [b.pubkey for b in state.builders]
    validator_pubkeys = [v.pubkey for v in state.validators]

    # [New in Gloas:EIP7732]
    # Regardless of the withdrawal credentials prefix, if a builder/validator
    # already exists with this pubkey, apply the deposit to their balance
    is_builder = deposit_request.pubkey in builder_pubkeys
    is_validator = deposit_request.pubkey in validator_pubkeys
    if is_builder or (
        is_builder_withdrawal_credential(deposit_request.withdrawal_credentials)
        and not is_validator
        and not is_pending_validator(state.pending_deposits, deposit_request.pubkey)
    ):
        # Apply builder deposits immediately
        apply_deposit_for_builder(
            state,
            deposit_request.pubkey,
            deposit_request.withdrawal_credentials,
            deposit_request.amount,
            deposit_request.signature,
            state.slot,
        )
        return

    # Add validator deposits to the queue
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

##### Voluntary exits

###### Modified `process_voluntary_exit`

```python
def process_voluntary_exit(state: BeaconState, signed_voluntary_exit: SignedVoluntaryExit) -> None:
    voluntary_exit = signed_voluntary_exit.message
    domain = compute_domain(
        DOMAIN_VOLUNTARY_EXIT, CAPELLA_FORK_VERSION, state.genesis_validators_root
    )
    signing_root = compute_signing_root(voluntary_exit, domain)

    # Exits must specify an epoch when they become valid; they are not valid before then
    assert get_current_epoch(state) >= voluntary_exit.epoch

    # [New in Gloas:EIP7732]
    if is_builder_index(voluntary_exit.validator_index):
        builder_index = convert_validator_index_to_builder_index(voluntary_exit.validator_index)
        # Verify the builder is active
        assert is_active_builder(state, builder_index)
        # Only exit builder if it has no pending withdrawals in the queue
        assert get_pending_balance_to_withdraw_for_builder(state, builder_index) == 0
        # Verify signature
        pubkey = state.builders[builder_index].pubkey
        assert bls.Verify(pubkey, signing_root, signed_voluntary_exit.signature)
        # Initiate exit
        initiate_builder_exit(state, builder_index)
        return

    validator = state.validators[voluntary_exit.validator_index]
    # Verify the validator is active
    assert is_active_validator(validator, get_current_epoch(state))
    # Verify exit has not been initiated
    assert validator.exit_epoch == FAR_FUTURE_EPOCH
    # Verify the validator has been active long enough
    assert get_current_epoch(state) >= validator.activation_epoch + SHARD_COMMITTEE_PERIOD
    # Only exit validator if it has no pending withdrawals in the queue
    assert get_pending_balance_to_withdraw(state, voluntary_exit.validator_index) == 0
    # Verify signature
    assert bls.Verify(validator.pubkey, signing_root, signed_voluntary_exit.signature)
    # Initiate exit
    initiate_validator_exit(state, voluntary_exit.validator_index)
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

##### Payload attestations

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
    indexed_payload_attestation = get_indexed_payload_attestation(state, payload_attestation)
    assert is_valid_indexed_payload_attestation(state, indexed_payload_attestation)
```

##### Proposer slashing

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
