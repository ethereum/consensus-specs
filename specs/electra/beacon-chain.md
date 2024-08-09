# Electra -- The Beacon Chain

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Misc](#misc)
  - [Withdrawal prefixes](#withdrawal-prefixes)
  - [Domains](#domains)
- [Preset](#preset)
  - [Gwei values](#gwei-values)
  - [Rewards and penalties](#rewards-and-penalties)
  - [State list lengths](#state-list-lengths)
  - [Max operations per block](#max-operations-per-block)
  - [Execution](#execution)
  - [Withdrawals processing](#withdrawals-processing)
- [Configuration](#configuration)
  - [Validator cycle](#validator-cycle)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`DepositRequest`](#depositrequest)
    - [`PendingBalanceDeposit`](#pendingbalancedeposit)
    - [`PendingPartialWithdrawal`](#pendingpartialwithdrawal)
    - [`WithdrawalRequest`](#withdrawalrequest)
    - [`ConsolidationRequest`](#consolidationrequest)
    - [`PendingConsolidation`](#pendingconsolidation)
  - [Modified Containers](#modified-containers)
    - [`AttesterSlashing`](#attesterslashing)
  - [Extended Containers](#extended-containers)
    - [`Attestation`](#attestation)
    - [`IndexedAttestation`](#indexedattestation)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
    - [`BeaconState`](#beaconstate)
- [Helper functions](#helper-functions)
  - [Predicates](#predicates)
    - [Modified `compute_proposer_index`](#modified-compute_proposer_index)
    - [Modified `is_eligible_for_activation_queue`](#modified-is_eligible_for_activation_queue)
    - [New `is_compounding_withdrawal_credential`](#new-is_compounding_withdrawal_credential)
    - [New `has_compounding_withdrawal_credential`](#new-has_compounding_withdrawal_credential)
    - [New `has_execution_withdrawal_credential`](#new-has_execution_withdrawal_credential)
    - [Modified `is_fully_withdrawable_validator`](#modified-is_fully_withdrawable_validator)
    - [Modified `is_partially_withdrawable_validator`](#modified-is_partially_withdrawable_validator)
  - [Misc](#misc-1)
    - [New `get_committee_indices`](#new-get_committee_indices)
    - [New `get_validator_max_effective_balance`](#new-get_validator_max_effective_balance)
  - [Beacon state accessors](#beacon-state-accessors)
    - [New `get_balance_churn_limit`](#new-get_balance_churn_limit)
    - [New `get_activation_exit_churn_limit`](#new-get_activation_exit_churn_limit)
    - [New `get_consolidation_churn_limit`](#new-get_consolidation_churn_limit)
    - [New `get_active_balance`](#new-get_active_balance)
    - [New `get_pending_balance_to_withdraw`](#new-get_pending_balance_to_withdraw)
    - [Modified `get_attesting_indices`](#modified-get_attesting_indices)
    - [Modified `get_next_sync_committee_indices`](#modified-get_next_sync_committee_indices)
  - [Beacon state mutators](#beacon-state-mutators)
    - [Modified `initiate_validator_exit`](#modified-initiate_validator_exit)
    - [New `switch_to_compounding_validator`](#new-switch_to_compounding_validator)
    - [New `queue_excess_active_balance`](#new-queue_excess_active_balance)
    - [New `queue_entire_balance_and_reset_validator`](#new-queue_entire_balance_and_reset_validator)
    - [New `compute_exit_epoch_and_update_churn`](#new-compute_exit_epoch_and_update_churn)
    - [New `compute_consolidation_epoch_and_update_churn`](#new-compute_consolidation_epoch_and_update_churn)
    - [Modified `slash_validator`](#modified-slash_validator)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [Modified `process_registry_updates`](#modified-process_registry_updates)
    - [New `process_pending_balance_deposits`](#new-process_pending_balance_deposits)
    - [New `process_pending_consolidations`](#new-process_pending_consolidations)
    - [Modified `process_effective_balance_updates`](#modified-process_effective_balance_updates)
  - [Block processing](#block-processing)
    - [Withdrawals](#withdrawals)
      - [Modified `get_expected_withdrawals`](#modified-get_expected_withdrawals)
      - [Modified `process_withdrawals`](#modified-process_withdrawals)
    - [Execution payload](#execution-payload)
      - [Modified `process_execution_payload`](#modified-process_execution_payload)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [Attestations](#attestations)
        - [Modified `process_attestation`](#modified-process_attestation)
      - [Deposits](#deposits)
        - [Modified `apply_deposit`](#modified-apply_deposit)
        - [New `is_valid_deposit_signature`](#new-is_valid_deposit_signature)
        - [Modified `add_validator_to_registry`](#modified-add_validator_to_registry)
        - [Modified `get_validator_from_deposit`](#modified-get_validator_from_deposit)
      - [Voluntary exits](#voluntary-exits)
        - [Modified `process_voluntary_exit`](#modified-process_voluntary_exit)
      - [Execution layer withdrawal requests](#execution-layer-withdrawal-requests)
        - [New `process_withdrawal_request`](#new-process_withdrawal_request)
      - [Deposit requests](#deposit-requests)
        - [New `process_deposit_request`](#new-process_deposit_request)
      - [Execution layer consolidation requests](#execution-layer-consolidation-requests)
        - [New `process_consolidation_request`](#new-process_consolidation_request)
- [Testing](#testing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

Electra is a consensus-layer upgrade containing a number of features. Including:
* [EIP-6110](https://eips.ethereum.org/EIPS/eip-6110): Supply validator deposits on chain
* [EIP-7002](https://eips.ethereum.org/EIPS/eip-7002): Execution layer triggerable exits
* [EIP-7251](https://eips.ethereum.org/EIPS/eip-7251): Increase the MAX_EFFECTIVE_BALANCE
* [EIP-7549](https://eips.ethereum.org/EIPS/eip-7549): Move committee index outside Attestation

*Note:* This specification is built upon [Deneb](../deneb/beacon_chain.md) and is under active development.

## Constants

The following values are (non-configurable) constants used throughout the specification.

### Misc

| Name | Value | Description |
| - | - | - |
| `UNSET_DEPOSIT_REQUESTS_START_INDEX` | `uint64(2**64 - 1)` | *[New in Electra:EIP6110]* |
| `FULL_EXIT_REQUEST_AMOUNT` | `uint64(0)` | *[New in Electra:EIP7002]* |

### Withdrawal prefixes

| Name | Value |
| - | - |
| `COMPOUNDING_WITHDRAWAL_PREFIX` | `Bytes1('0x02')` |

### Domains

| Name | Value |
| - | - |
| `DOMAIN_CONSOLIDATION` | `DomainType('0x0B000000')` |

## Preset

### Gwei values

| Name | Value |
| - | - |
| `MIN_ACTIVATION_BALANCE` | `Gwei(2**5 * 10**9)`  (= 32,000,000,000) |
| `MAX_EFFECTIVE_BALANCE_ELECTRA` | `Gwei(2**11 * 10**9)` (= 2048,000,000,000) |

### Rewards and penalties

| Name | Value |
| - | - |
| `MIN_SLASHING_PENALTY_QUOTIENT_ELECTRA` | `uint64(2**12)`  (= 4,096) |
| `WHISTLEBLOWER_REWARD_QUOTIENT_ELECTRA` | `uint64(2**12)`  (= 4,096) |

### State list lengths

| Name | Value | Unit |
| - | - | :-: |
| `PENDING_BALANCE_DEPOSITS_LIMIT` | `uint64(2**27)` (= 134,217,728) | pending balance deposits |
| `PENDING_PARTIAL_WITHDRAWALS_LIMIT` | `uint64(2**27)` (= 134,217,728) | pending partial withdrawals |
| `PENDING_CONSOLIDATIONS_LIMIT` | `uint64(2**18)` (= 262,144) | pending consolidations |

### Max operations per block

| Name | Value |
| - | - |
| `MAX_ATTESTER_SLASHINGS_ELECTRA`   | `2**0` (= 1) | *[New in Electra:EIP7549]* |
| `MAX_ATTESTATIONS_ELECTRA` | `2**3` (= 8) | *[New in Electra:EIP7549]* |

### Execution

| Name | Value | Description |
| - | - | - |
| `MAX_DEPOSIT_REQUESTS_PER_PAYLOAD` | `uint64(2**13)` (= 8,192) | *[New in Electra:EIP6110]* Maximum number of deposit receipts allowed in each payload |
| `MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD` | `uint64(2**4)` (= 16)| *[New in Electra:EIP7002]* Maximum number of execution layer withdrawal requests in each payload |
| `MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD` | `uint64(1)` (= 1) | *[New in Electra:EIP7002]* Maximum number of execution layer consolidation requests in each payload |

### Withdrawals processing

| Name | Value | Description |
| - | - | - |
| `MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP` | `uint64(2**3)` (= 8)| *[New in Electra:EIP7002]* Maximum number of pending partial withdrawals to process per payload |

## Configuration

### Validator cycle

| Name | Value |
| - | - |
| `MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA` | `Gwei(2**7 * 10**9)` (= 128,000,000,000) | # Equivalent to 4 32 ETH validators
| `MAX_PER_EPOCH_ACTIVATION_EXIT_CHURN_LIMIT` | `Gwei(2**8 * 10**9)` (= 256,000,000,000) |

## Containers

### New containers

#### `DepositRequest`

*Note*: The container is new in EIP6110.

```python
class DepositRequest(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
    amount: Gwei
    signature: BLSSignature
    index: uint64
```

#### `PendingBalanceDeposit`

*Note*: The container is new in EIP7251.

```python
class PendingBalanceDeposit(Container):
    index: ValidatorIndex
    amount: Gwei
```

#### `PendingPartialWithdrawal`

*Note*: The container is new in EIP7251.

```python
class PendingPartialWithdrawal(Container):
    index: ValidatorIndex
    amount: Gwei
    withdrawable_epoch: Epoch
```
#### `WithdrawalRequest`

*Note*: The container is new in EIP7251:EIP7002.

```python
class WithdrawalRequest(Container):
    source_address: ExecutionAddress
    validator_pubkey: BLSPubkey
    amount: Gwei
```

#### `ConsolidationRequest`

*Note*: The container is new in EIP7251.

```python
class ConsolidationRequest(Container):
    source_address: ExecutionAddress
    source_pubkey: BLSPubkey
    target_pubkey: BLSPubkey
```

#### `PendingConsolidation`

*Note*: The container is new in EIP7251.

```python
class PendingConsolidation(Container):
    source_index: ValidatorIndex
    target_index: ValidatorIndex
```

### Modified Containers

#### `AttesterSlashing`

```python
class AttesterSlashing(Container):
    attestation_1: IndexedAttestation  # [Modified in Electra:EIP7549]
    attestation_2: IndexedAttestation  # [Modified in Electra:EIP7549]
```

### Extended Containers

#### `Attestation`

```python
class Attestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT]  # [Modified in Electra:EIP7549]
    data: AttestationData
    signature: BLSSignature
    committee_bits: Bitvector[MAX_COMMITTEES_PER_SLOT]  # [New in Electra:EIP7549]
```

#### `IndexedAttestation`

```python
class IndexedAttestation(Container):
    # [Modified in Electra:EIP7549]
    attesting_indices: List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT]
    data: AttestationData
    signature: BLSSignature
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data  # Eth1 data vote
    graffiti: Bytes32  # Arbitrary data
    # Operations
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS_ELECTRA]  # [Modified in Electra:EIP7549]
    attestations: List[Attestation, MAX_ATTESTATIONS_ELECTRA]  # [Modified in Electra:EIP7549]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    # Execution
    execution_payload: ExecutionPayload  # [Modified in Electra:EIP6110:EIP7002]
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
```

#### `ExecutionPayload`

```python
class ExecutionPayload(Container):
    # Execution block header fields
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
    # Extra payload fields
    block_hash: Hash32
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]
    blob_gas_used: uint64
    excess_blob_gas: uint64
    deposit_requests: List[DepositRequest, MAX_DEPOSIT_REQUESTS_PER_PAYLOAD]  # [New in Electra:EIP6110]
    # [New in Electra:EIP7002:EIP7251]
    withdrawal_requests: List[WithdrawalRequest, MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD]
    # [New in Electra:EIP7251]
    consolidation_requests: List[ConsolidationRequest, MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD]
```

#### `ExecutionPayloadHeader`

```python
class ExecutionPayloadHeader(Container):
    # Execution block header fields
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
    # Extra payload fields
    block_hash: Hash32
    transactions_root: Root
    withdrawals_root: Root
    blob_gas_used: uint64
    excess_blob_gas: uint64
    deposit_requests_root: Root  # [New in Electra:EIP6110]
    withdrawal_requests_root: Root  # [New in Electra:EIP7002:EIP7251]
    consolidation_requests_root: Root  # [New in Electra:EIP7251]
```

#### `BeaconState`

```python
class BeaconState(Container):
    # Versioning
    genesis_time: uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    # History
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]
    # Eth1
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH]
    eth1_deposit_index: uint64
    # Registry
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    # Randomness
    randao_mixes: Vector[Bytes32, EPOCHS_PER_HISTORICAL_VECTOR]
    # Slashings
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]  # Per-epoch sums of slashed effective balances
    # Participation
    previous_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    current_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    # Inactivity
    inactivity_scores: List[uint64, VALIDATOR_REGISTRY_LIMIT]
    # Sync
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # Execution
    latest_execution_payload_header: ExecutionPayloadHeader  # [Modified in Electra:EIP6110:EIP7002]
    # Withdrawals
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    # Deep history valid from Capella onwards
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
    deposit_requests_start_index: uint64  # [New in Electra:EIP6110]
    deposit_balance_to_consume: Gwei  # [New in Electra:EIP7251]
    exit_balance_to_consume: Gwei  # [New in Electra:EIP7251]
    earliest_exit_epoch: Epoch  # [New in Electra:EIP7251]
    consolidation_balance_to_consume: Gwei  # [New in Electra:EIP7251]
    earliest_consolidation_epoch: Epoch  # [New in Electra:EIP7251]
    pending_balance_deposits: List[PendingBalanceDeposit, PENDING_BALANCE_DEPOSITS_LIMIT]  # [New in Electra:EIP7251]
    # [New in Electra:EIP7251]
    pending_partial_withdrawals: List[PendingPartialWithdrawal, PENDING_PARTIAL_WITHDRAWALS_LIMIT]
    pending_consolidations: List[PendingConsolidation, PENDING_CONSOLIDATIONS_LIMIT]  # [New in Electra:EIP7251]
```

## Helper functions

### Predicates

#### Modified `compute_proposer_index`

*Note*: The function `compute_proposer_index` is modified to use `MAX_EFFECTIVE_BALANCE_ELECTRA`.

```python
def compute_proposer_index(state: BeaconState, indices: Sequence[ValidatorIndex], seed: Bytes32) -> ValidatorIndex:
    """
    Return from ``indices`` a random index sampled by effective balance.
    """
    assert len(indices) > 0
    MAX_RANDOM_BYTE = 2**8 - 1
    i = uint64(0)
    total = uint64(len(indices))
    while True:
        candidate_index = indices[compute_shuffled_index(i % total, total, seed)]
        random_byte = hash(seed + uint_to_bytes(uint64(i // 32)))[i % 32]
        effective_balance = state.validators[candidate_index].effective_balance
        # [Modified in Electra:EIP7251]
        if effective_balance * MAX_RANDOM_BYTE >= MAX_EFFECTIVE_BALANCE_ELECTRA * random_byte:
            return candidate_index
        i += 1
```

#### Modified `is_eligible_for_activation_queue`

*Note*: The function `is_eligible_for_activation_queue` is modified to use `MIN_ACTIVATION_BALANCE` instead of `MAX_EFFECTIVE_BALANCE`.

```python
def is_eligible_for_activation_queue(validator: Validator) -> bool:
    """
    Check if ``validator`` is eligible to be placed into the activation queue.
    """
    return (
        validator.activation_eligibility_epoch == FAR_FUTURE_EPOCH
        and validator.effective_balance >= MIN_ACTIVATION_BALANCE  # [Modified in Electra:EIP7251]
    )
```

#### New `is_compounding_withdrawal_credential`

```python
def is_compounding_withdrawal_credential(withdrawal_credentials: Bytes32) -> bool:
    return withdrawal_credentials[:1] == COMPOUNDING_WITHDRAWAL_PREFIX
```

#### New `has_compounding_withdrawal_credential`

```python
def has_compounding_withdrawal_credential(validator: Validator) -> bool:
    """
    Check if ``validator`` has an 0x02 prefixed "compounding" withdrawal credential.
    """
    return is_compounding_withdrawal_credential(validator.withdrawal_credentials)
```

#### New `has_execution_withdrawal_credential`

```python
def has_execution_withdrawal_credential(validator: Validator) -> bool:
    """
    Check if ``validator`` has a 0x01 or 0x02 prefixed withdrawal credential.
    """
    return has_compounding_withdrawal_credential(validator) or has_eth1_withdrawal_credential(validator)
```

#### Modified `is_fully_withdrawable_validator`

*Note*: The function `is_fully_withdrawable_validator` is modified to use `has_execution_withdrawal_credential` instead of `has_eth1_withdrawal_credential`.

```python
def is_fully_withdrawable_validator(validator: Validator, balance: Gwei, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is fully withdrawable.
    """
    return (
        has_execution_withdrawal_credential(validator)  # [Modified in Electra:EIP7251]
        and validator.withdrawable_epoch <= epoch
        and balance > 0
    )
```

#### Modified `is_partially_withdrawable_validator`

*Note*: The function `is_partially_withdrawable_validator` is modified to use `get_validator_max_effective_balance` instead of `MAX_EFFECTIVE_BALANCE` and `has_execution_withdrawal_credential` instead of `has_eth1_withdrawal_credential`.

```python
def is_partially_withdrawable_validator(validator: Validator, balance: Gwei) -> bool:
    """
    Check if ``validator`` is partially withdrawable.
    """
    max_effective_balance = get_validator_max_effective_balance(validator)
    has_max_effective_balance = validator.effective_balance == max_effective_balance  # [Modified in Electra:EIP7251]
    has_excess_balance = balance > max_effective_balance  # [Modified in Electra:EIP7251]
    return (
        has_execution_withdrawal_credential(validator)  # [Modified in Electra:EIP7251]
        and has_max_effective_balance
        and has_excess_balance
    )
```

### Misc

#### New `get_committee_indices`

```python
def get_committee_indices(committee_bits: Bitvector) -> Sequence[CommitteeIndex]:
    return [CommitteeIndex(index) for index, bit in enumerate(committee_bits) if bit]
```

#### New `get_validator_max_effective_balance`

```python
def get_validator_max_effective_balance(validator: Validator) -> Gwei:
    """
    Get max effective balance for ``validator``.
    """
    if has_compounding_withdrawal_credential(validator):
        return MAX_EFFECTIVE_BALANCE_ELECTRA
    else:
        return MIN_ACTIVATION_BALANCE
```

### Beacon state accessors

#### New `get_balance_churn_limit`

```python
def get_balance_churn_limit(state: BeaconState) -> Gwei:
    """
    Return the churn limit for the current epoch.
    """
    churn = max(
        MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        get_total_active_balance(state) // CHURN_LIMIT_QUOTIENT
    )
    return churn - churn % EFFECTIVE_BALANCE_INCREMENT
```

#### New `get_activation_exit_churn_limit`

```python
def get_activation_exit_churn_limit(state: BeaconState) -> Gwei:
    """
    Return the churn limit for the current epoch dedicated to activations and exits.
    """
    return min(MAX_PER_EPOCH_ACTIVATION_EXIT_CHURN_LIMIT, get_balance_churn_limit(state))
```

#### New `get_consolidation_churn_limit`

```python
def get_consolidation_churn_limit(state: BeaconState) -> Gwei:
    return get_balance_churn_limit(state) - get_activation_exit_churn_limit(state)
```

#### New `get_active_balance`

```python
def get_active_balance(state: BeaconState, validator_index: ValidatorIndex) -> Gwei:
    max_effective_balance = get_validator_max_effective_balance(state.validators[validator_index])
    return min(state.balances[validator_index], max_effective_balance)
```

#### New `get_pending_balance_to_withdraw`

```python
def get_pending_balance_to_withdraw(state: BeaconState, validator_index: ValidatorIndex) -> Gwei:
    return sum(
        withdrawal.amount for withdrawal in state.pending_partial_withdrawals if withdrawal.index == validator_index
    )
```

#### Modified `get_attesting_indices`

*Note*: The function `get_attesting_indices` is modified to support EIP7549.

```python
def get_attesting_indices(state: BeaconState, attestation: Attestation) -> Set[ValidatorIndex]:
    """
    Return the set of attesting indices corresponding to ``aggregation_bits`` and ``committee_bits``.
    """
    output: Set[ValidatorIndex] = set()
    committee_indices = get_committee_indices(attestation.committee_bits)
    committee_offset = 0
    for index in committee_indices:
        committee = get_beacon_committee(state, attestation.data.slot, index)
        committee_attesters = set(
            index for i, index in enumerate(committee) if attestation.aggregation_bits[committee_offset + i])
        output = output.union(committee_attesters)

        committee_offset += len(committee)

    return output
```

#### Modified `get_next_sync_committee_indices`

*Note*: The function `get_next_sync_committee_indices` is modified to use `MAX_EFFECTIVE_BALANCE_ELECTRA`.

```python
def get_next_sync_committee_indices(state: BeaconState) -> Sequence[ValidatorIndex]:
    """
    Return the sync committee indices, with possible duplicates, for the next sync committee.
    """
    epoch = Epoch(get_current_epoch(state) + 1)

    MAX_RANDOM_BYTE = 2**8 - 1
    active_validator_indices = get_active_validator_indices(state, epoch)
    active_validator_count = uint64(len(active_validator_indices))
    seed = get_seed(state, epoch, DOMAIN_SYNC_COMMITTEE)
    i = 0
    sync_committee_indices: List[ValidatorIndex] = []
    while len(sync_committee_indices) < SYNC_COMMITTEE_SIZE:
        shuffled_index = compute_shuffled_index(uint64(i % active_validator_count), active_validator_count, seed)
        candidate_index = active_validator_indices[shuffled_index]
        random_byte = hash(seed + uint_to_bytes(uint64(i // 32)))[i % 32]
        effective_balance = state.validators[candidate_index].effective_balance
        # [Modified in Electra:EIP7251]
        if effective_balance * MAX_RANDOM_BYTE >= MAX_EFFECTIVE_BALANCE_ELECTRA * random_byte:
            sync_committee_indices.append(candidate_index)
        i += 1
    return sync_committee_indices
```

### Beacon state mutators

#### Modified `initiate_validator_exit`

*Note*: The function `initiate_validator_exit` is modified to use the new `compute_exit_epoch_and_update_churn` function.

```python
def initiate_validator_exit(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Initiate the exit of the validator with index ``index``.
    """
    # Return if validator already initiated exit
    validator = state.validators[index]
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return

    # Compute exit queue epoch [Modified in Electra:EIP7251]
    exit_queue_epoch = compute_exit_epoch_and_update_churn(state, validator.effective_balance)

    # Set validator exit epoch and withdrawable epoch
    validator.exit_epoch = exit_queue_epoch
    validator.withdrawable_epoch = Epoch(validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY)
```

#### New `switch_to_compounding_validator`

```python
def switch_to_compounding_validator(state: BeaconState, index: ValidatorIndex) -> None:
    validator = state.validators[index]
    if has_eth1_withdrawal_credential(validator):
        validator.withdrawal_credentials = COMPOUNDING_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]
        queue_excess_active_balance(state, index)
```

#### New `queue_excess_active_balance`

```python
def queue_excess_active_balance(state: BeaconState, index: ValidatorIndex) -> None:
    balance = state.balances[index]
    if balance > MIN_ACTIVATION_BALANCE:
        excess_balance = balance - MIN_ACTIVATION_BALANCE
        state.balances[index] = MIN_ACTIVATION_BALANCE
        state.pending_balance_deposits.append(
            PendingBalanceDeposit(index=index, amount=excess_balance)
        )
```

#### New `queue_entire_balance_and_reset_validator`

```python
def queue_entire_balance_and_reset_validator(state: BeaconState, index: ValidatorIndex) -> None:
    balance = state.balances[index]
    state.balances[index] = 0
    validator = state.validators[index]
    validator.effective_balance = 0
    validator.activation_eligibility_epoch = FAR_FUTURE_EPOCH
    state.pending_balance_deposits.append(
        PendingBalanceDeposit(index=index, amount=balance)
    )
```

#### New `compute_exit_epoch_and_update_churn`

```python
def compute_exit_epoch_and_update_churn(state: BeaconState, exit_balance: Gwei) -> Epoch:
    earliest_exit_epoch = max(state.earliest_exit_epoch, compute_activation_exit_epoch(get_current_epoch(state)))
    per_epoch_churn = get_activation_exit_churn_limit(state)
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

#### New `compute_consolidation_epoch_and_update_churn`

```python
def compute_consolidation_epoch_and_update_churn(state: BeaconState, consolidation_balance: Gwei) -> Epoch:
    earliest_consolidation_epoch = max(
        state.earliest_consolidation_epoch, compute_activation_exit_epoch(get_current_epoch(state)))
    per_epoch_consolidation_churn = get_consolidation_churn_limit(state)
    # New epoch for consolidations.
    if state.earliest_consolidation_epoch < earliest_consolidation_epoch:
        consolidation_balance_to_consume = per_epoch_consolidation_churn
    else:
        consolidation_balance_to_consume = state.consolidation_balance_to_consume

    # Consolidation doesn't fit in the current earliest epoch.
    if consolidation_balance > consolidation_balance_to_consume:
        balance_to_process = consolidation_balance - consolidation_balance_to_consume
        additional_epochs = (balance_to_process - 1) // per_epoch_consolidation_churn + 1
        earliest_consolidation_epoch += additional_epochs
        consolidation_balance_to_consume += additional_epochs * per_epoch_consolidation_churn

    # Consume the balance and update state variables.
    state.consolidation_balance_to_consume = consolidation_balance_to_consume - consolidation_balance
    state.earliest_consolidation_epoch = earliest_consolidation_epoch

    return state.earliest_consolidation_epoch
```

#### Modified `slash_validator`

*Note*: The function `slash_validator` is modified to change how the slashing penalty and proposer/whistleblower rewards are calculated in accordance with EIP7251.

```python
def slash_validator(state: BeaconState,
                    slashed_index: ValidatorIndex,
                    whistleblower_index: ValidatorIndex=None) -> None:
    """
    Slash the validator with index ``slashed_index``.
    """
    epoch = get_current_epoch(state)
    initiate_validator_exit(state, slashed_index)
    validator = state.validators[slashed_index]
    validator.slashed = True
    validator.withdrawable_epoch = max(validator.withdrawable_epoch, Epoch(epoch + EPOCHS_PER_SLASHINGS_VECTOR))
    state.slashings[epoch % EPOCHS_PER_SLASHINGS_VECTOR] += validator.effective_balance
    # [Modified in Electra:EIP7251]
    slashing_penalty = validator.effective_balance // MIN_SLASHING_PENALTY_QUOTIENT_ELECTRA
    decrease_balance(state, slashed_index, slashing_penalty)

    # Apply proposer and whistleblower rewards
    proposer_index = get_beacon_proposer_index(state)
    if whistleblower_index is None:
        whistleblower_index = proposer_index
    whistleblower_reward = Gwei(
        validator.effective_balance // WHISTLEBLOWER_REWARD_QUOTIENT_ELECTRA)  # [Modified in Electra:EIP7251]
    proposer_reward = Gwei(whistleblower_reward * PROPOSER_WEIGHT // WEIGHT_DENOMINATOR)
    increase_balance(state, proposer_index, proposer_reward)
    increase_balance(state, whistleblower_index, Gwei(whistleblower_reward - proposer_reward))
```

## Beacon chain state transition function

### Epoch processing

#### Modified `process_epoch`

*Note*: The function `process_epoch` is modified to call updated functions and to process pending balance deposits and pending consolidations which are new in Electra.

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)  # [Modified in Electra:EIP7251]
    process_slashings(state)
    process_eth1_data_reset(state)
    process_pending_balance_deposits(state)  # [New in Electra:EIP7251]
    process_pending_consolidations(state)  # [New in Electra:EIP7251]
    process_effective_balance_updates(state)  # [Modified in Electra:EIP7251]
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
```

#### Modified `process_registry_updates`

*Note*: The function `process_registry_updates` is modified to use the updated definition of `initiate_validator_exit`
and changes how the activation epochs are computed for eligible validators.

```python
def process_registry_updates(state: BeaconState) -> None:
    # Process activation eligibility and ejections
    for index, validator in enumerate(state.validators):
        if is_eligible_for_activation_queue(validator):
            validator.activation_eligibility_epoch = get_current_epoch(state) + 1

        if (
            is_active_validator(validator, get_current_epoch(state))
            and validator.effective_balance <= EJECTION_BALANCE
        ):
            initiate_validator_exit(state, ValidatorIndex(index))

    # Activate all eligible validators
    activation_epoch = compute_activation_exit_epoch(get_current_epoch(state))
    for validator in state.validators:
        if is_eligible_for_activation(state, validator):
            validator.activation_epoch = activation_epoch
```

#### New `process_pending_balance_deposits`

```python
def process_pending_balance_deposits(state: BeaconState) -> None:
    next_epoch = Epoch(get_current_epoch(state) + 1)
    available_for_processing = state.deposit_balance_to_consume + get_activation_exit_churn_limit(state)
    processed_amount = 0
    next_deposit_index = 0
    deposits_to_postpone = []

    for deposit in state.pending_balance_deposits:
        validator = state.validators[deposit.index]
        # Validator is exiting, postpone the deposit until after withdrawable epoch
        if validator.exit_epoch < FAR_FUTURE_EPOCH:
            if next_epoch <= validator.withdrawable_epoch:
                deposits_to_postpone.append(deposit)
            # Deposited balance will never become active. Increase balance but do not consume churn
            else:
                increase_balance(state, deposit.index, deposit.amount)
        # Validator is not exiting, attempt to process deposit
        else:
            # Deposit does not fit in the churn, no more deposit processing in this epoch.
            if processed_amount + deposit.amount > available_for_processing:
                break
            # Deposit fits in the churn, process it. Increase balance and consume churn.
            else: 
                increase_balance(state, deposit.index, deposit.amount)
                processed_amount += deposit.amount
        # Regardless of how the deposit was handled, we move on in the queue.
        next_deposit_index += 1

    state.pending_balance_deposits = state.pending_balance_deposits[next_deposit_index:]

    if len(state.pending_balance_deposits) == 0:
        state.deposit_balance_to_consume = Gwei(0)
    else:
        state.deposit_balance_to_consume = available_for_processing - processed_amount

    state.pending_balance_deposits += deposits_to_postpone
```

#### New `process_pending_consolidations`

```python
def process_pending_consolidations(state: BeaconState) -> None:
    next_epoch = Epoch(get_current_epoch(state) + 1)
    next_pending_consolidation = 0
    for pending_consolidation in state.pending_consolidations:
        source_validator = state.validators[pending_consolidation.source_index]
        if source_validator.slashed:
            next_pending_consolidation += 1
            continue
        if source_validator.withdrawable_epoch > next_epoch:
            break

        # Churn any target excess active balance of target and raise its max
        switch_to_compounding_validator(state, pending_consolidation.target_index)
        # Move active balance to target. Excess balance is withdrawable.
        active_balance = get_active_balance(state, pending_consolidation.source_index)
        decrease_balance(state, pending_consolidation.source_index, active_balance)
        increase_balance(state, pending_consolidation.target_index, active_balance)
        next_pending_consolidation += 1

    state.pending_consolidations = state.pending_consolidations[next_pending_consolidation:]
```

#### Modified `process_effective_balance_updates`

*Note*: The function `process_effective_balance_updates` is modified to use the new limit for the maximum effective balance.

```python
def process_effective_balance_updates(state: BeaconState) -> None:
    # Update effective balances with hysteresis
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        HYSTERESIS_INCREMENT = uint64(EFFECTIVE_BALANCE_INCREMENT // HYSTERESIS_QUOTIENT)
        DOWNWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_DOWNWARD_MULTIPLIER
        UPWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_UPWARD_MULTIPLIER
        # [Modified in Electra:EIP7251]
        EFFECTIVE_BALANCE_LIMIT = (
            MAX_EFFECTIVE_BALANCE_ELECTRA if has_compounding_withdrawal_credential(validator)
            else MIN_ACTIVATION_BALANCE
        )

        if (
            balance + DOWNWARD_THRESHOLD < validator.effective_balance
            or validator.effective_balance + UPWARD_THRESHOLD < balance
        ):
            validator.effective_balance = min(balance - balance % EFFECTIVE_BALANCE_INCREMENT, EFFECTIVE_BALANCE_LIMIT)
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_withdrawals(state, block.body.execution_payload)  # [Modified in Electra:EIP7251]
    process_execution_payload(state, block.body, EXECUTION_ENGINE)  # [Modified in Electra:EIP6110]
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)  # [Modified in Electra:EIP6110:EIP7002:EIP7549:EIP7251]
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### Withdrawals

##### Modified `get_expected_withdrawals`

*Note*: The function `get_expected_withdrawals` is modified to support EIP7251.

```python
def get_expected_withdrawals(state: BeaconState) -> Tuple[Sequence[Withdrawal], uint64]:
    epoch = get_current_epoch(state)
    withdrawal_index = state.next_withdrawal_index
    validator_index = state.next_withdrawal_validator_index
    withdrawals: List[Withdrawal] = []

    # [New in Electra:EIP7251] Consume pending partial withdrawals
    for withdrawal in state.pending_partial_withdrawals:
        if withdrawal.withdrawable_epoch > epoch or len(withdrawals) == MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP:
            break

        validator = state.validators[withdrawal.index]
        has_sufficient_effective_balance = validator.effective_balance >= MIN_ACTIVATION_BALANCE
        has_excess_balance = state.balances[withdrawal.index] > MIN_ACTIVATION_BALANCE
        if validator.exit_epoch == FAR_FUTURE_EPOCH and has_sufficient_effective_balance and has_excess_balance:
            withdrawable_balance = min(state.balances[withdrawal.index] - MIN_ACTIVATION_BALANCE, withdrawal.amount)
            withdrawals.append(Withdrawal(
                index=withdrawal_index,
                validator_index=withdrawal.index,
                address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                amount=withdrawable_balance,
            ))
            withdrawal_index += WithdrawalIndex(1)

    partial_withdrawals_count = len(withdrawals)

    # Sweep for remaining.
    bound = min(len(state.validators), MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
    for _ in range(bound):
        validator = state.validators[validator_index]
        balance = state.balances[validator_index]
        if is_fully_withdrawable_validator(validator, balance, epoch):
            withdrawals.append(Withdrawal(
                index=withdrawal_index,
                validator_index=validator_index,
                address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                amount=balance,
            ))
            withdrawal_index += WithdrawalIndex(1)
        elif is_partially_withdrawable_validator(validator, balance):
            withdrawals.append(Withdrawal(
                index=withdrawal_index,
                validator_index=validator_index,
                address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                amount=balance - get_validator_max_effective_balance(validator),  # [Modified in Electra:EIP7251]
            ))
            withdrawal_index += WithdrawalIndex(1)
        if len(withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
            break
        validator_index = ValidatorIndex((validator_index + 1) % len(state.validators))
    return withdrawals, partial_withdrawals_count
```

##### Modified `process_withdrawals`

*Note*: The function `process_withdrawals` is modified to support EIP7251.

```python
def process_withdrawals(state: BeaconState, payload: ExecutionPayload) -> None:
    expected_withdrawals, partial_withdrawals_count = get_expected_withdrawals(state)  # [Modified in Electra:EIP7251]

    assert len(payload.withdrawals) == len(expected_withdrawals)

    for expected_withdrawal, withdrawal in zip(expected_withdrawals, payload.withdrawals):
        assert withdrawal == expected_withdrawal
        decrease_balance(state, withdrawal.validator_index, withdrawal.amount)

    # Update pending partial withdrawals [New in Electra:EIP7251]
    state.pending_partial_withdrawals = state.pending_partial_withdrawals[partial_withdrawals_count:]

    # Update the next withdrawal index if this block contained withdrawals
    if len(expected_withdrawals) != 0:
        latest_withdrawal = expected_withdrawals[-1]
        state.next_withdrawal_index = WithdrawalIndex(latest_withdrawal.index + 1)

    # Update the next validator index to start the next withdrawal sweep
    if len(expected_withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
        # Next sweep starts after the latest withdrawal's validator index
        next_validator_index = ValidatorIndex((expected_withdrawals[-1].validator_index + 1) % len(state.validators))
        state.next_withdrawal_validator_index = next_validator_index
    else:
        # Advance sweep by the max length of the sweep if there was not a full set of withdrawals
        next_index = state.next_withdrawal_validator_index + MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
        next_validator_index = ValidatorIndex(next_index % len(state.validators))
        state.next_withdrawal_validator_index = next_validator_index
```

#### Execution payload

##### Modified `process_execution_payload`

*Note*: The function `process_execution_payload` is modified to use the new `ExecutionPayloadHeader` type.

```python
def process_execution_payload(state: BeaconState, body: BeaconBlockBody, execution_engine: ExecutionEngine) -> None:
    payload = body.execution_payload

    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)
    # Verify commitments are under limit
    assert len(body.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK
    # Verify the execution payload is valid
    versioned_hashes = [kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments]
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
        )
    )
    # Cache execution payload header
    state.latest_execution_payload_header = ExecutionPayloadHeader(
        parent_hash=payload.parent_hash,
        fee_recipient=payload.fee_recipient,
        state_root=payload.state_root,
        receipts_root=payload.receipts_root,
        logs_bloom=payload.logs_bloom,
        prev_randao=payload.prev_randao,
        block_number=payload.block_number,
        gas_limit=payload.gas_limit,
        gas_used=payload.gas_used,
        timestamp=payload.timestamp,
        extra_data=payload.extra_data,
        base_fee_per_gas=payload.base_fee_per_gas,
        block_hash=payload.block_hash,
        transactions_root=hash_tree_root(payload.transactions),
        withdrawals_root=hash_tree_root(payload.withdrawals),
        blob_gas_used=payload.blob_gas_used,
        excess_blob_gas=payload.excess_blob_gas,
        deposit_requests_root=hash_tree_root(payload.deposit_requests),  # [New in Electra:EIP6110]
        withdrawal_requests_root=hash_tree_root(payload.withdrawal_requests),  # [New in Electra:EIP7002:EIP7251]
        consolidation_requests_root=hash_tree_root(payload.consolidation_requests),  # [New in Electra:EIP7251]
    )
```

#### Operations

##### Modified `process_operations`

*Note*: The function `process_operations` is modified to support all of the new functionality in Electra.

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # [Modified in Electra:EIP6110]
    # Disable former deposit mechanism once all prior deposits are processed
    eth1_deposit_index_limit = min(state.eth1_data.deposit_count, state.deposit_requests_start_index)
    if state.eth1_deposit_index < eth1_deposit_index_limit:
        assert len(body.deposits) == min(MAX_DEPOSITS, eth1_deposit_index_limit - state.eth1_deposit_index)
    else:
        assert len(body.deposits) == 0

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    for_ops(body.attestations, process_attestation)  # [Modified in Electra:EIP7549]
    for_ops(body.deposits, process_deposit)  # [Modified in Electra:EIP7251]
    for_ops(body.voluntary_exits, process_voluntary_exit)  # [Modified in Electra:EIP7251]
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    for_ops(body.execution_payload.deposit_requests, process_deposit_request)  # [New in Electra:EIP6110]
    # [New in Electra:EIP7002:EIP7251]
    for_ops(body.execution_payload.withdrawal_requests, process_withdrawal_request)
    # [New in Electra:EIP7251]
    for_ops(body.execution_payload.consolidation_requests, process_consolidation_request)
```

##### Attestations

###### Modified `process_attestation`

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.target.epoch == compute_epoch_at_slot(data.slot)
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot

    # [Modified in Electra:EIP7549]
    assert data.index == 0
    committee_indices = get_committee_indices(attestation.committee_bits)
    participants_count = 0
    for index in committee_indices:
        assert index < get_committee_count_per_slot(state, data.target.epoch)
        committee = get_beacon_committee(state, data.slot, index)
        participants_count += len(committee)

    assert len(attestation.aggregation_bits) == participants_count

    # Participation flag indices
    participation_flag_indices = get_attestation_participation_flag_indices(state, data, state.slot - data.slot)

    # Verify signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))

    # Update epoch participation flags
    if data.target.epoch == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation

    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, attestation):
        for flag_index, weight in enumerate(PARTICIPATION_FLAG_WEIGHTS):
            if flag_index in participation_flag_indices and not has_flag(epoch_participation[index], flag_index):
                epoch_participation[index] = add_flag(epoch_participation[index], flag_index)
                proposer_reward_numerator += get_base_reward(state, index) * weight

    # Reward proposer
    proposer_reward_denominator = (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT) * WEIGHT_DENOMINATOR // PROPOSER_WEIGHT
    proposer_reward = Gwei(proposer_reward_numerator // proposer_reward_denominator)
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
```

##### Deposits

###### Modified `apply_deposit`

*Note*: The function `process_deposit` is modified to support EIP7251.

```python
def apply_deposit(state: BeaconState,
                  pubkey: BLSPubkey,
                  withdrawal_credentials: Bytes32,
                  amount: uint64,
                  signature: BLSSignature) -> None:
    validator_pubkeys = [v.pubkey for v in state.validators]
    if pubkey not in validator_pubkeys:
        # Verify the deposit signature (proof of possession) which is not checked by the deposit contract
        if is_valid_deposit_signature(pubkey, withdrawal_credentials, amount, signature):
            add_validator_to_registry(state, pubkey, withdrawal_credentials, amount)
    else:
        # Increase balance by deposit amount
        index = ValidatorIndex(validator_pubkeys.index(pubkey))
        state.pending_balance_deposits.append(
            PendingBalanceDeposit(index=index, amount=amount)
        )  # [Modified in Electra:EIP7251]
        # Check if valid deposit switch to compounding credentials
        if (
            is_compounding_withdrawal_credential(withdrawal_credentials)
            and has_eth1_withdrawal_credential(state.validators[index])
            and is_valid_deposit_signature(pubkey, withdrawal_credentials, amount, signature)
        ):
            switch_to_compounding_validator(state, index)

```

###### New `is_valid_deposit_signature`

```python
def is_valid_deposit_signature(pubkey: BLSPubkey,
                               withdrawal_credentials: Bytes32,
                               amount: uint64,
                               signature: BLSSignature) -> bool:
    deposit_message = DepositMessage(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
    )
    domain = compute_domain(DOMAIN_DEPOSIT)  # Fork-agnostic domain since deposits are valid across forks
    signing_root = compute_signing_root(deposit_message, domain)
    return bls.Verify(pubkey, signing_root, signature)
```

###### Modified `add_validator_to_registry`

*Note*: The function `add_validator_to_registry` is modified to initialize the validator with a balance of zero and add a pending balance deposit to the queue.

```python
def add_validator_to_registry(state: BeaconState,
                              pubkey: BLSPubkey,
                              withdrawal_credentials: Bytes32,
                              amount: uint64) -> None:
    index = get_index_for_new_validator(state)
    validator = get_validator_from_deposit(pubkey, withdrawal_credentials)
    set_or_append_list(state.validators, index, validator)
    set_or_append_list(state.balances, index, 0)  # [Modified in Electra:EIP7251]
    set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.inactivity_scores, index, uint64(0))
    state.pending_balance_deposits.append(PendingBalanceDeposit(index=index, amount=amount))  # [New in Electra:EIP7251]
```

###### Modified `get_validator_from_deposit`

*Note*: The function `get_validator_from_deposit` is modified to initialize the validator with an effective balance of zero.

```python
def get_validator_from_deposit(pubkey: BLSPubkey, withdrawal_credentials: Bytes32) -> Validator:
    return Validator(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
        effective_balance=0,  # [Modified in Electra:EIP7251]
    )
```

##### Voluntary exits

###### Modified `process_voluntary_exit`

*Note*: The function `process_voluntary_exit` is modified to ensure the validator has no pending withdrawals in the queue.

```python
def process_voluntary_exit(state: BeaconState, signed_voluntary_exit: SignedVoluntaryExit) -> None:
    voluntary_exit = signed_voluntary_exit.message
    validator = state.validators[voluntary_exit.validator_index]
    # Verify the validator is active
    assert is_active_validator(validator, get_current_epoch(state))
    # Verify exit has not been initiated
    assert validator.exit_epoch == FAR_FUTURE_EPOCH
    # Exits must specify an epoch when they become valid; they are not valid before then
    assert get_current_epoch(state) >= voluntary_exit.epoch
    # Verify the validator has been active long enough
    assert get_current_epoch(state) >= validator.activation_epoch + SHARD_COMMITTEE_PERIOD
    # Only exit validator if it has no pending withdrawals in the queue
    assert get_pending_balance_to_withdraw(state, voluntary_exit.validator_index) == 0  # [New in Electra:EIP7251]
    # Verify signature
    domain = compute_domain(DOMAIN_VOLUNTARY_EXIT, CAPELLA_FORK_VERSION, state.genesis_validators_root)
    signing_root = compute_signing_root(voluntary_exit, domain)
    assert bls.Verify(validator.pubkey, signing_root, signed_voluntary_exit.signature)
    # Initiate exit
    initiate_validator_exit(state, voluntary_exit.validator_index)
```

##### Execution layer withdrawal requests

###### New `process_withdrawal_request`

```python
def process_withdrawal_request(
    state: BeaconState,
    withdrawal_request: WithdrawalRequest
) -> None:
    amount = withdrawal_request.amount
    is_full_exit_request = amount == FULL_EXIT_REQUEST_AMOUNT

    # If partial withdrawal queue is full, only full exits are processed
    if len(state.pending_partial_withdrawals) == PENDING_PARTIAL_WITHDRAWALS_LIMIT and not is_full_exit_request:
        return

    validator_pubkeys = [v.pubkey for v in state.validators]
    # Verify pubkey exists
    request_pubkey = withdrawal_request.validator_pubkey
    if request_pubkey not in validator_pubkeys:
        return
    index = ValidatorIndex(validator_pubkeys.index(request_pubkey))
    validator = state.validators[index]

    # Verify withdrawal credentials
    has_correct_credential = has_execution_withdrawal_credential(validator)
    is_correct_source_address = (
        validator.withdrawal_credentials[12:] == withdrawal_request.source_address
    )
    if not (has_correct_credential and is_correct_source_address):
        return
    # Verify the validator is active
    if not is_active_validator(validator, get_current_epoch(state)):
        return
    # Verify exit has not been initiated
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return
    # Verify the validator has been active long enough
    if get_current_epoch(state) < validator.activation_epoch + SHARD_COMMITTEE_PERIOD:
        return

    pending_balance_to_withdraw = get_pending_balance_to_withdraw(state, index)

    if is_full_exit_request:
        # Only exit validator if it has no pending withdrawals in the queue
        if pending_balance_to_withdraw == 0:
            initiate_validator_exit(state, index)
        return

    has_sufficient_effective_balance = validator.effective_balance >= MIN_ACTIVATION_BALANCE
    has_excess_balance = state.balances[index] > MIN_ACTIVATION_BALANCE + pending_balance_to_withdraw

    # Only allow partial withdrawals with compounding withdrawal credentials
    if has_compounding_withdrawal_credential(validator) and has_sufficient_effective_balance and has_excess_balance:
        to_withdraw = min(
            state.balances[index] - MIN_ACTIVATION_BALANCE - pending_balance_to_withdraw,
            amount
        )
        exit_queue_epoch = compute_exit_epoch_and_update_churn(state, to_withdraw)
        withdrawable_epoch = Epoch(exit_queue_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY)
        state.pending_partial_withdrawals.append(PendingPartialWithdrawal(
            index=index,
            amount=to_withdraw,
            withdrawable_epoch=withdrawable_epoch,
        ))
```

##### Deposit requests

###### New `process_deposit_request`

```python
def process_deposit_request(state: BeaconState, deposit_request: DepositRequest) -> None:
    # Set deposit request start index
    if state.deposit_requests_start_index == UNSET_DEPOSIT_REQUESTS_START_INDEX:
        state.deposit_requests_start_index = deposit_request.index

    apply_deposit(
        state=state,
        pubkey=deposit_request.pubkey,
        withdrawal_credentials=deposit_request.withdrawal_credentials,
        amount=deposit_request.amount,
        signature=deposit_request.signature,
    )
```

##### Execution layer consolidation requests

###### New `process_consolidation_request`

```python
def process_consolidation_request(
    state: BeaconState,
    consolidation_request: ConsolidationRequest
) -> None:
    # If the pending consolidations queue is full, consolidation requests are ignored
    if len(state.pending_consolidations) == PENDING_CONSOLIDATIONS_LIMIT:
        return
    # If there is too little available consolidation churn limit, consolidation requests are ignored
    if get_consolidation_churn_limit(state) <= MIN_ACTIVATION_BALANCE:
        return

    validator_pubkeys = [v.pubkey for v in state.validators]
    # Verify pubkeys exists
    request_source_pubkey = consolidation_request.source_pubkey
    request_target_pubkey = consolidation_request.target_pubkey
    if request_source_pubkey not in validator_pubkeys:
        return
    if request_target_pubkey not in validator_pubkeys:
        return
    source_index = ValidatorIndex(validator_pubkeys.index(request_source_pubkey))
    target_index = ValidatorIndex(validator_pubkeys.index(request_target_pubkey))
    source_validator = state.validators[source_index]
    target_validator = state.validators[target_index]

    # Verify that source != target, so a consolidation cannot be used as an exit.
    if source_index == target_index:
        return

    # Verify source withdrawal credentials
    has_correct_credential = has_execution_withdrawal_credential(source_validator)
    is_correct_source_address = (
        source_validator.withdrawal_credentials[12:] == consolidation_request.source_address
    )
    if not (has_correct_credential and is_correct_source_address):
        return

    # Verify that target has execution withdrawal credentials
    if not has_execution_withdrawal_credential(target_validator):
        return

    # Verify the source and the target are active
    current_epoch = get_current_epoch(state)
    if not is_active_validator(source_validator, current_epoch):
        return
    if not is_active_validator(target_validator, current_epoch):
        return
    # Verify exits for source and target have not been initiated
    if source_validator.exit_epoch != FAR_FUTURE_EPOCH:
        return
    if target_validator.exit_epoch != FAR_FUTURE_EPOCH:
        return

    # Initiate source validator exit and append pending consolidation
    source_validator.exit_epoch = compute_consolidation_epoch_and_update_churn(
        state, source_validator.effective_balance
    )
    source_validator.withdrawable_epoch = Epoch(
        source_validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    state.pending_consolidations.append(PendingConsolidation(
        source_index=source_index,
        target_index=target_index
    ))
```

## Testing

*Note*: The function `initialize_beacon_state_from_eth1` is modified for pure Electra testing only.
Modifications include:
1. Use `ELECTRA_FORK_VERSION` as the previous and current fork version.
2. Utilize the Electra `BeaconBlockBody` when constructing the initial `latest_block_header`.
3. *[New in Electra:EIP6110]* Add `deposit_requests_start_index` variable to the genesis state initialization.
4. *[New in Electra:EIP7251]* Initialize new fields to support increasing the maximum effective balance.

```python
def initialize_beacon_state_from_eth1(eth1_block_hash: Hash32,
                                      eth1_timestamp: uint64,
                                      deposits: Sequence[Deposit],
                                      execution_payload_header: ExecutionPayloadHeader=ExecutionPayloadHeader()
                                      ) -> BeaconState:
    fork = Fork(
        previous_version=ELECTRA_FORK_VERSION,  # [Modified in Electra:EIP6110] for testing only
        current_version=ELECTRA_FORK_VERSION,  # [Modified in Electra:EIP6110]
        epoch=GENESIS_EPOCH,
    )
    state = BeaconState(
        genesis_time=eth1_timestamp + GENESIS_DELAY,
        fork=fork,
        eth1_data=Eth1Data(block_hash=eth1_block_hash, deposit_count=uint64(len(deposits))),
        latest_block_header=BeaconBlockHeader(body_root=hash_tree_root(BeaconBlockBody())),
        randao_mixes=[eth1_block_hash] * EPOCHS_PER_HISTORICAL_VECTOR,  # Seed RANDAO with Eth1 entropy
        deposit_requests_start_index=UNSET_DEPOSIT_REQUESTS_START_INDEX,  # [New in Electra:EIP6110]
    )

    # Process deposits
    leaves = list(map(lambda deposit: deposit.data, deposits))
    for index, deposit in enumerate(deposits):
        deposit_data_list = List[DepositData, 2**DEPOSIT_CONTRACT_TREE_DEPTH](*leaves[:index + 1])
        state.eth1_data.deposit_root = hash_tree_root(deposit_data_list)
        process_deposit(state, deposit)

    # Process deposit balance updates
    for deposit in state.pending_balance_deposits:
        increase_balance(state, deposit.index, deposit.amount)
    state.pending_balance_deposits = []

    # Process activations
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        # [Modified in Electra:EIP7251]
        validator.effective_balance = min(
            balance - balance % EFFECTIVE_BALANCE_INCREMENT, get_validator_max_effective_balance(validator))
        if validator.effective_balance >= MIN_ACTIVATION_BALANCE:
            validator.activation_eligibility_epoch = GENESIS_EPOCH
            validator.activation_epoch = GENESIS_EPOCH

    # Set genesis validators root for domain separation and chain versioning
    state.genesis_validators_root = hash_tree_root(state.validators)

    # Fill in sync committees
    # Note: A duplicate committee is assigned for the current and next committee at genesis
    state.current_sync_committee = get_next_sync_committee(state)
    state.next_sync_committee = get_next_sync_committee(state)

    # Initialize the execution payload header
    state.latest_execution_payload_header = execution_payload_header

    return state
```
