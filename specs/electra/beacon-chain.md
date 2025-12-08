# Electra -- The Beacon Chain

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Misc](#misc)
  - [Withdrawal prefixes](#withdrawal-prefixes)
  - [Execution layer triggered requests](#execution-layer-triggered-requests)
- [Preset](#preset)
  - [Gwei values](#gwei-values)
  - [Rewards and penalties](#rewards-and-penalties)
  - [State list lengths](#state-list-lengths)
  - [Max operations per block](#max-operations-per-block)
  - [Execution](#execution)
  - [Withdrawals processing](#withdrawals-processing)
  - [Pending deposits processing](#pending-deposits-processing)
- [Configuration](#configuration)
  - [Execution](#execution-1)
  - [Validator cycle](#validator-cycle)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`PendingDeposit`](#pendingdeposit)
    - [`PendingPartialWithdrawal`](#pendingpartialwithdrawal)
    - [`PendingConsolidation`](#pendingconsolidation)
    - [`DepositRequest`](#depositrequest)
    - [`WithdrawalRequest`](#withdrawalrequest)
    - [`ConsolidationRequest`](#consolidationrequest)
    - [`ExecutionRequests`](#executionrequests)
    - [`SingleAttestation`](#singleattestation)
  - [Modified containers](#modified-containers)
    - [`AttesterSlashing`](#attesterslashing)
    - [`BeaconBlockBody`](#beaconblockbody)
  - [Modified containers](#modified-containers-1)
    - [`Attestation`](#attestation)
    - [`IndexedAttestation`](#indexedattestation)
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
    - [New `is_eligible_for_partial_withdrawals`](#new-is_eligible_for_partial_withdrawals)
  - [Misc](#misc-1)
    - [New `get_committee_indices`](#new-get_committee_indices)
    - [New `get_max_effective_balance`](#new-get_max_effective_balance)
  - [Beacon state accessors](#beacon-state-accessors)
    - [New `get_balance_churn_limit`](#new-get_balance_churn_limit)
    - [New `get_activation_exit_churn_limit`](#new-get_activation_exit_churn_limit)
    - [New `get_consolidation_churn_limit`](#new-get_consolidation_churn_limit)
    - [New `get_pending_balance_to_withdraw`](#new-get_pending_balance_to_withdraw)
    - [Modified `get_attesting_indices`](#modified-get_attesting_indices)
    - [Modified `get_next_sync_committee_indices`](#modified-get_next_sync_committee_indices)
  - [Beacon state mutators](#beacon-state-mutators)
    - [Modified `initiate_validator_exit`](#modified-initiate_validator_exit)
    - [New `switch_to_compounding_validator`](#new-switch_to_compounding_validator)
    - [New `queue_excess_active_balance`](#new-queue_excess_active_balance)
    - [New `compute_exit_epoch_and_update_churn`](#new-compute_exit_epoch_and_update_churn)
    - [New `compute_consolidation_epoch_and_update_churn`](#new-compute_consolidation_epoch_and_update_churn)
    - [Modified `slash_validator`](#modified-slash_validator)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Modified `process_epoch`](#modified-process_epoch)
    - [Modified `process_registry_updates`](#modified-process_registry_updates)
    - [Modified `process_slashings`](#modified-process_slashings)
    - [New `apply_pending_deposit`](#new-apply_pending_deposit)
    - [New `process_pending_deposits`](#new-process_pending_deposits)
    - [New `process_pending_consolidations`](#new-process_pending_consolidations)
    - [Modified `process_effective_balance_updates`](#modified-process_effective_balance_updates)
  - [Execution engine](#execution-engine)
    - [Request data](#request-data)
      - [Modified `NewPayloadRequest`](#modified-newpayloadrequest)
    - [Engine APIs](#engine-apis)
      - [Modified `is_valid_block_hash`](#modified-is_valid_block_hash)
      - [Modified `notify_new_payload`](#modified-notify_new_payload)
      - [Modified `verify_and_notify_new_payload`](#modified-verify_and_notify_new_payload)
  - [Block processing](#block-processing)
    - [Withdrawals](#withdrawals)
      - [New `get_pending_partial_withdrawals`](#new-get_pending_partial_withdrawals)
      - [Modified `get_sweep_withdrawals`](#modified-get_sweep_withdrawals)
      - [Modified `get_expected_withdrawals`](#modified-get_expected_withdrawals)
      - [Modified `process_withdrawals`](#modified-process_withdrawals)
    - [Execution payload](#execution-payload)
      - [New `get_execution_requests_list`](#new-get_execution_requests_list)
      - [Modified `process_execution_payload`](#modified-process_execution_payload)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [Attestations](#attestations)
        - [Modified `process_attestation`](#modified-process_attestation)
      - [Deposits](#deposits)
        - [Modified `get_validator_from_deposit`](#modified-get_validator_from_deposit)
        - [Modified `add_validator_to_registry`](#modified-add_validator_to_registry)
        - [Modified `apply_deposit`](#modified-apply_deposit)
        - [New `is_valid_deposit_signature`](#new-is_valid_deposit_signature)
        - [Modified `process_deposit`](#modified-process_deposit)
      - [Voluntary exits](#voluntary-exits)
        - [Modified `process_voluntary_exit`](#modified-process_voluntary_exit)
      - [Execution layer withdrawal requests](#execution-layer-withdrawal-requests)
        - [New `process_withdrawal_request`](#new-process_withdrawal_request)
      - [Deposit requests](#deposit-requests)
        - [New `process_deposit_request`](#new-process_deposit_request)
      - [Execution layer consolidation requests](#execution-layer-consolidation-requests)
        - [New `is_valid_switch_to_compounding_request`](#new-is_valid_switch_to_compounding_request)
        - [New `process_consolidation_request`](#new-process_consolidation_request)

<!-- mdformat-toc end -->

## Introduction

Electra is a consensus-layer upgrade containing a number of features. Including:

- [EIP-6110](https://eips.ethereum.org/EIPS/eip-6110): Supply validator deposits
  on chain
- [EIP-7002](https://eips.ethereum.org/EIPS/eip-7002): Execution layer
  triggerable exits
- [EIP-7251](https://eips.ethereum.org/EIPS/eip-7251): Increase the
  MAX_EFFECTIVE_BALANCE
- [EIP-7549](https://eips.ethereum.org/EIPS/eip-7549): Move committee index
  outside Attestation
- [EIP-7691](https://eips.ethereum.org/EIPS/eip-7691): Blob throughput increase

*Note*: This specification is built upon [Deneb](../deneb/beacon-chain.md).

## Constants

The following values are (non-configurable) constants used throughout the
specification.

### Misc

| Name                                 | Value               | Description                                                                       |
| ------------------------------------ | ------------------- | --------------------------------------------------------------------------------- |
| `UNSET_DEPOSIT_REQUESTS_START_INDEX` | `uint64(2**64 - 1)` | *[New in Electra:EIP6110]* Value which indicates no start index has been assigned |
| `FULL_EXIT_REQUEST_AMOUNT`           | `uint64(0)`         | *[New in Electra:EIP7002]* Withdrawal amount used to signal a full validator exit |

### Withdrawal prefixes

| Name                            | Value            | Description                                                                         |
| ------------------------------- | ---------------- | ----------------------------------------------------------------------------------- |
| `COMPOUNDING_WITHDRAWAL_PREFIX` | `Bytes1('0x02')` | *[New in Electra:EIP7251]* Withdrawal credential prefix for a compounding validator |

### Execution layer triggered requests

| Name                         | Value            |
| ---------------------------- | ---------------- |
| `DEPOSIT_REQUEST_TYPE`       | `Bytes1('0x00')` |
| `WITHDRAWAL_REQUEST_TYPE`    | `Bytes1('0x01')` |
| `CONSOLIDATION_REQUEST_TYPE` | `Bytes1('0x02')` |

## Preset

### Gwei values

| Name                            | Value                                      | Description                                                                      |
| ------------------------------- | ------------------------------------------ | -------------------------------------------------------------------------------- |
| `MIN_ACTIVATION_BALANCE`        | `Gwei(2**5 * 10**9)` (= 32,000,000,000)    | *[New in Electra:EIP7251]* Minimum balance for a validator to become active      |
| `MAX_EFFECTIVE_BALANCE_ELECTRA` | `Gwei(2**11 * 10**9)` (= 2048,000,000,000) | *[New in Electra:EIP7251]* Maximum effective balance for a compounding validator |

### Rewards and penalties

| Name                                    | Value                     |
| --------------------------------------- | ------------------------- |
| `MIN_SLASHING_PENALTY_QUOTIENT_ELECTRA` | `uint64(2**12)` (= 4,096) |
| `WHISTLEBLOWER_REWARD_QUOTIENT_ELECTRA` | `uint64(2**12)` (= 4,096) |

### State list lengths

| Name                                | Value                           | Unit                        |
| ----------------------------------- | ------------------------------- | --------------------------- |
| `PENDING_DEPOSITS_LIMIT`            | `uint64(2**27)` (= 134,217,728) | pending deposits            |
| `PENDING_PARTIAL_WITHDRAWALS_LIMIT` | `uint64(2**27)` (= 134,217,728) | pending partial withdrawals |
| `PENDING_CONSOLIDATIONS_LIMIT`      | `uint64(2**18)` (= 262,144)     | pending consolidations      |

### Max operations per block

| Name                             | Value        |
| -------------------------------- | ------------ |
| `MAX_ATTESTER_SLASHINGS_ELECTRA` | `2**0` (= 1) |
| `MAX_ATTESTATIONS_ELECTRA`       | `2**3` (= 8) |

### Execution

| Name                                     | Value                     | Description                                                                                         |
| ---------------------------------------- | ------------------------- | --------------------------------------------------------------------------------------------------- |
| `MAX_DEPOSIT_REQUESTS_PER_PAYLOAD`       | `uint64(2**13)` (= 8,192) | *[New in Electra:EIP6110]* Maximum number of execution layer deposit requests in each payload       |
| `MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD`    | `uint64(2**4)` (= 16)     | *[New in Electra:EIP7002]* Maximum number of execution layer withdrawal requests in each payload    |
| `MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD` | `uint64(2**1)` (= 2)      | *[New in Electra:EIP7251]* Maximum number of execution layer consolidation requests in each payload |

### Withdrawals processing

| Name                                         | Value                | Description                                                                                     |
| -------------------------------------------- | -------------------- | ----------------------------------------------------------------------------------------------- |
| `MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP` | `uint64(2**3)` (= 8) | *[New in Electra:EIP7002]* Maximum number of pending partial withdrawals to process per payload |

### Pending deposits processing

| Name                             | Value                 | Description                                                                        |
| -------------------------------- | --------------------- | ---------------------------------------------------------------------------------- |
| `MAX_PENDING_DEPOSITS_PER_EPOCH` | `uint64(2**4)` (= 16) | *[New in Electra:EIP6110]* Maximum number of pending deposits to process per epoch |

## Configuration

### Execution

| Name                          | Value       | Description                                                                                                      |
| ----------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------- |
| `MAX_BLOBS_PER_BLOCK_ELECTRA` | `uint64(9)` | *[New in Electra:EIP7691]* Maximum number of blobs in a single block limited by `MAX_BLOB_COMMITMENTS_PER_BLOCK` |

### Validator cycle

| Name                                        | Value                                    |
| ------------------------------------------- | ---------------------------------------- |
| `MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA`         | `Gwei(2**7 * 10**9)` (= 128,000,000,000) |
| `MAX_PER_EPOCH_ACTIVATION_EXIT_CHURN_LIMIT` | `Gwei(2**8 * 10**9)` (= 256,000,000,000) |

## Containers

### New containers

#### `PendingDeposit`

*Note*: The container is new in EIP7251.

```python
class PendingDeposit(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
    amount: Gwei
    signature: BLSSignature
    slot: Slot
```

#### `PendingPartialWithdrawal`

*Note*: The container is new in EIP7251.

```python
class PendingPartialWithdrawal(Container):
    validator_index: ValidatorIndex
    amount: Gwei
    withdrawable_epoch: Epoch
```

#### `PendingConsolidation`

*Note*: The container is new in EIP7251.

```python
class PendingConsolidation(Container):
    source_index: ValidatorIndex
    target_index: ValidatorIndex
```

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

#### `ExecutionRequests`

```python
class ExecutionRequests(Container):
    # [New in Electra:EIP6110]
    deposits: List[DepositRequest, MAX_DEPOSIT_REQUESTS_PER_PAYLOAD]
    # [New in Electra:EIP7002:EIP7251]
    withdrawals: List[WithdrawalRequest, MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD]
    # [New in Electra:EIP7251]
    consolidations: List[ConsolidationRequest, MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD]
```

#### `SingleAttestation`

```python
class SingleAttestation(Container):
    committee_index: CommitteeIndex
    attester_index: ValidatorIndex
    data: AttestationData
    signature: BLSSignature
```

### Modified containers

#### `AttesterSlashing`

```python
class AttesterSlashing(Container):
    # [Modified in Electra:EIP7549]
    attestation_1: IndexedAttestation
    # [Modified in Electra:EIP7549]
    attestation_2: IndexedAttestation
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    # [Modified in Electra:EIP7549]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS_ELECTRA]
    # [Modified in Electra:EIP7549]
    attestations: List[Attestation, MAX_ATTESTATIONS_ELECTRA]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    execution_payload: ExecutionPayload
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    # [New in Electra]
    execution_requests: ExecutionRequests
```

### Modified containers

#### `Attestation`

```python
class Attestation(Container):
    # [Modified in Electra:EIP7549]
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT]
    data: AttestationData
    signature: BLSSignature
    # [New in Electra:EIP7549]
    committee_bits: Bitvector[MAX_COMMITTEES_PER_SLOT]
```

#### `IndexedAttestation`

```python
class IndexedAttestation(Container):
    # [Modified in Electra:EIP7549]
    attesting_indices: List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT]
    data: AttestationData
    signature: BLSSignature
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
    latest_execution_payload_header: ExecutionPayloadHeader
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
    # [New in Electra:EIP6110]
    deposit_requests_start_index: uint64
    # [New in Electra:EIP7251]
    deposit_balance_to_consume: Gwei
    # [New in Electra:EIP7251]
    exit_balance_to_consume: Gwei
    # [New in Electra:EIP7251]
    earliest_exit_epoch: Epoch
    # [New in Electra:EIP7251]
    consolidation_balance_to_consume: Gwei
    # [New in Electra:EIP7251]
    earliest_consolidation_epoch: Epoch
    # [New in Electra:EIP7251]
    pending_deposits: List[PendingDeposit, PENDING_DEPOSITS_LIMIT]
    # [New in Electra:EIP7251]
    pending_partial_withdrawals: List[PendingPartialWithdrawal, PENDING_PARTIAL_WITHDRAWALS_LIMIT]
    # [New in Electra:EIP7251]
    pending_consolidations: List[PendingConsolidation, PENDING_CONSOLIDATIONS_LIMIT]
```

## Helper functions

### Predicates

#### Modified `compute_proposer_index`

*Note*: The function `compute_proposer_index` is modified to use
`MAX_EFFECTIVE_BALANCE_ELECTRA` and to use a 16-bit random value instead of an
8-bit random byte in the effective balance filter.

```python
def compute_proposer_index(
    state: BeaconState, indices: Sequence[ValidatorIndex], seed: Bytes32
) -> ValidatorIndex:
    """
    Return from ``indices`` a random index sampled by effective balance.
    """
    assert len(indices) > 0
    # [Modified in Electra]
    MAX_RANDOM_VALUE = 2**16 - 1
    i = uint64(0)
    total = uint64(len(indices))
    while True:
        candidate_index = indices[compute_shuffled_index(i % total, total, seed)]
        # [Modified in Electra]
        random_bytes = hash(seed + uint_to_bytes(i // 16))
        offset = i % 16 * 2
        random_value = bytes_to_uint64(random_bytes[offset : offset + 2])
        effective_balance = state.validators[candidate_index].effective_balance
        # [Modified in Electra:EIP7251]
        if effective_balance * MAX_RANDOM_VALUE >= MAX_EFFECTIVE_BALANCE_ELECTRA * random_value:
            return candidate_index
        i += 1
```

#### Modified `is_eligible_for_activation_queue`

*Note*: The function `is_eligible_for_activation_queue` is modified to use
`MIN_ACTIVATION_BALANCE` instead of `MAX_EFFECTIVE_BALANCE`.

```python
def is_eligible_for_activation_queue(validator: Validator) -> bool:
    """
    Check if ``validator`` is eligible to be placed into the activation queue.
    """
    return (
        validator.activation_eligibility_epoch == FAR_FUTURE_EPOCH
        # [Modified in Electra:EIP7251]
        and validator.effective_balance >= MIN_ACTIVATION_BALANCE
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
    return (
        has_eth1_withdrawal_credential(validator)  # 0x01
        or has_compounding_withdrawal_credential(validator)  # 0x02
    )
```

#### Modified `is_fully_withdrawable_validator`

*Note*: The function `is_fully_withdrawable_validator` is modified to use
`has_execution_withdrawal_credential` instead of
`has_eth1_withdrawal_credential`.

```python
def is_fully_withdrawable_validator(validator: Validator, balance: Gwei, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is fully withdrawable.
    """
    return (
        # [Modified in Electra:EIP7251]
        has_execution_withdrawal_credential(validator)
        and validator.withdrawable_epoch <= epoch
        and balance > 0
    )
```

#### Modified `is_partially_withdrawable_validator`

*Note*: The function `is_partially_withdrawable_validator` is modified to use
`get_max_effective_balance` instead of `MAX_EFFECTIVE_BALANCE` and
`has_execution_withdrawal_credential` instead of
`has_eth1_withdrawal_credential`.

```python
def is_partially_withdrawable_validator(validator: Validator, balance: Gwei) -> bool:
    """
    Check if ``validator`` is partially withdrawable.
    """
    max_effective_balance = get_max_effective_balance(validator)
    # [Modified in Electra:EIP7251]
    has_max_effective_balance = validator.effective_balance == max_effective_balance
    # [Modified in Electra:EIP7251]
    has_excess_balance = balance > max_effective_balance
    return (
        # [Modified in Electra:EIP7251]
        has_execution_withdrawal_credential(validator)
        and has_max_effective_balance
        and has_excess_balance
    )
```

#### New `is_eligible_for_partial_withdrawals`

```python
def is_eligible_for_partial_withdrawals(validator: Validator, balance: Gwei) -> bool:
    """
    Check if ``validator`` can process a pending partial withdrawal.
    """
    has_sufficient_effective_balance = validator.effective_balance >= MIN_ACTIVATION_BALANCE
    has_excess_balance = balance > MIN_ACTIVATION_BALANCE
    return (
        validator.exit_epoch == FAR_FUTURE_EPOCH
        and has_sufficient_effective_balance
        and has_excess_balance
    )
```

### Misc

#### New `get_committee_indices`

```python
def get_committee_indices(committee_bits: Bitvector) -> Sequence[CommitteeIndex]:
    return [CommitteeIndex(index) for index, bit in enumerate(committee_bits) if bit]
```

#### New `get_max_effective_balance`

```python
def get_max_effective_balance(validator: Validator) -> Gwei:
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
        MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA, get_total_active_balance(state) // CHURN_LIMIT_QUOTIENT
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

#### New `get_pending_balance_to_withdraw`

```python
def get_pending_balance_to_withdraw(state: BeaconState, validator_index: ValidatorIndex) -> Gwei:
    return sum(
        withdrawal.amount
        for withdrawal in state.pending_partial_withdrawals
        if withdrawal.validator_index == validator_index
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
    for committee_index in committee_indices:
        committee = get_beacon_committee(state, attestation.data.slot, committee_index)
        committee_attesters = set(
            attester_index
            for i, attester_index in enumerate(committee)
            if attestation.aggregation_bits[committee_offset + i]
        )
        output = output.union(committee_attesters)

        committee_offset += len(committee)

    return output
```

#### Modified `get_next_sync_committee_indices`

*Note*: The function `get_next_sync_committee_indices` is modified to use
`MAX_EFFECTIVE_BALANCE_ELECTRA` and to use a 16-bit random value instead of an
8-bit random byte in the effective balance filter.

```python
def get_next_sync_committee_indices(state: BeaconState) -> Sequence[ValidatorIndex]:
    """
    Return the sync committee indices, with possible duplicates, for the next sync committee.
    """
    epoch = Epoch(get_current_epoch(state) + 1)

    # [Modified in Electra]
    MAX_RANDOM_VALUE = 2**16 - 1
    active_validator_indices = get_active_validator_indices(state, epoch)
    active_validator_count = uint64(len(active_validator_indices))
    seed = get_seed(state, epoch, DOMAIN_SYNC_COMMITTEE)
    i = uint64(0)
    sync_committee_indices: List[ValidatorIndex] = []
    while len(sync_committee_indices) < SYNC_COMMITTEE_SIZE:
        shuffled_index = compute_shuffled_index(
            uint64(i % active_validator_count), active_validator_count, seed
        )
        candidate_index = active_validator_indices[shuffled_index]
        # [Modified in Electra]
        random_bytes = hash(seed + uint_to_bytes(i // 16))
        offset = i % 16 * 2
        random_value = bytes_to_uint64(random_bytes[offset : offset + 2])
        effective_balance = state.validators[candidate_index].effective_balance
        # [Modified in Electra:EIP7251]
        if effective_balance * MAX_RANDOM_VALUE >= MAX_EFFECTIVE_BALANCE_ELECTRA * random_value:
            sync_committee_indices.append(candidate_index)
        i += 1
    return sync_committee_indices
```

### Beacon state mutators

#### Modified `initiate_validator_exit`

*Note*: The function `initiate_validator_exit` is modified to use the new
`compute_exit_epoch_and_update_churn` function.

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
    validator.withdrawal_credentials = (
        COMPOUNDING_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]
    )
    queue_excess_active_balance(state, index)
```

#### New `queue_excess_active_balance`

```python
def queue_excess_active_balance(state: BeaconState, index: ValidatorIndex) -> None:
    balance = state.balances[index]
    if balance > MIN_ACTIVATION_BALANCE:
        excess_balance = balance - MIN_ACTIVATION_BALANCE
        state.balances[index] = MIN_ACTIVATION_BALANCE
        validator = state.validators[index]
        # Use bls.G2_POINT_AT_INFINITY as a signature field placeholder
        # and GENESIS_SLOT to distinguish from a pending deposit request
        state.pending_deposits.append(
            PendingDeposit(
                pubkey=validator.pubkey,
                withdrawal_credentials=validator.withdrawal_credentials,
                amount=excess_balance,
                signature=bls.G2_POINT_AT_INFINITY,
                slot=GENESIS_SLOT,
            )
        )
```

#### New `compute_exit_epoch_and_update_churn`

```python
def compute_exit_epoch_and_update_churn(state: BeaconState, exit_balance: Gwei) -> Epoch:
    earliest_exit_epoch = max(
        state.earliest_exit_epoch, compute_activation_exit_epoch(get_current_epoch(state))
    )
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
def compute_consolidation_epoch_and_update_churn(
    state: BeaconState, consolidation_balance: Gwei
) -> Epoch:
    earliest_consolidation_epoch = max(
        state.earliest_consolidation_epoch, compute_activation_exit_epoch(get_current_epoch(state))
    )
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
    state.consolidation_balance_to_consume = (
        consolidation_balance_to_consume - consolidation_balance
    )
    state.earliest_consolidation_epoch = earliest_consolidation_epoch

    return state.earliest_consolidation_epoch
```

#### Modified `slash_validator`

*Note*: The function `slash_validator` is modified to change how the slashing
penalty and proposer/whistleblower rewards are calculated in accordance with
EIP7251.

```python
def slash_validator(
    state: BeaconState, slashed_index: ValidatorIndex, whistleblower_index: ValidatorIndex = None
) -> None:
    """
    Slash the validator with index ``slashed_index``.
    """
    epoch = get_current_epoch(state)
    initiate_validator_exit(state, slashed_index)
    validator = state.validators[slashed_index]
    validator.slashed = True
    validator.withdrawable_epoch = max(
        validator.withdrawable_epoch, Epoch(epoch + EPOCHS_PER_SLASHINGS_VECTOR)
    )
    state.slashings[epoch % EPOCHS_PER_SLASHINGS_VECTOR] += validator.effective_balance
    # [Modified in Electra:EIP7251]
    slashing_penalty = validator.effective_balance // MIN_SLASHING_PENALTY_QUOTIENT_ELECTRA
    decrease_balance(state, slashed_index, slashing_penalty)

    # Apply proposer and whistleblower rewards
    proposer_index = get_beacon_proposer_index(state)
    if whistleblower_index is None:
        whistleblower_index = proposer_index
    # [Modified in Electra:EIP7251]
    whistleblower_reward = Gwei(
        validator.effective_balance // WHISTLEBLOWER_REWARD_QUOTIENT_ELECTRA
    )
    proposer_reward = Gwei(whistleblower_reward * PROPOSER_WEIGHT // WEIGHT_DENOMINATOR)
    increase_balance(state, proposer_index, proposer_reward)
    increase_balance(state, whistleblower_index, Gwei(whistleblower_reward - proposer_reward))
```

## Beacon chain state transition function

### Epoch processing

#### Modified `process_epoch`

*Note*: The function `process_epoch` is modified to call updated functions and
to process pending balance deposits and pending consolidations which are new in
Electra.

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    # [Modified in Electra:EIP7251]
    process_registry_updates(state)
    # [Modified in Electra:EIP7251]
    process_slashings(state)
    process_eth1_data_reset(state)
    # [New in Electra:EIP7251]
    process_pending_deposits(state)
    # [New in Electra:EIP7251]
    process_pending_consolidations(state)
    # [Modified in Electra:EIP7251]
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
```

#### Modified `process_registry_updates`

*Note*: The function `process_registry_updates` is modified to use the updated
definitions of `initiate_validator_exit` and `is_eligible_for_activation_queue`,
changes how the activation epochs are computed for eligible validators, and
processes activations in the same loop as activation eligibility updates and
ejections.

```python
def process_registry_updates(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    activation_epoch = compute_activation_exit_epoch(current_epoch)

    # Process activation eligibility, ejections, and activations
    for index, validator in enumerate(state.validators):
        # [Modified in Electra:EIP7251]
        if is_eligible_for_activation_queue(validator):
            validator.activation_eligibility_epoch = current_epoch + 1
        elif (
            is_active_validator(validator, current_epoch)
            and validator.effective_balance <= EJECTION_BALANCE
        ):
            # [Modified in Electra:EIP7251]
            initiate_validator_exit(state, ValidatorIndex(index))
        elif is_eligible_for_activation(state, validator):
            validator.activation_epoch = activation_epoch
```

#### Modified `process_slashings`

*Note*: The function `process_slashings` is modified to use a new algorithm to
compute correlation penalty.

```python
def process_slashings(state: BeaconState) -> None:
    epoch = get_current_epoch(state)
    total_balance = get_total_active_balance(state)
    adjusted_total_slashing_balance = min(
        sum(state.slashings) * PROPORTIONAL_SLASHING_MULTIPLIER_BELLATRIX, total_balance
    )
    increment = (
        EFFECTIVE_BALANCE_INCREMENT  # Factored out from total balance to avoid uint64 overflow
    )
    penalty_per_effective_balance_increment = adjusted_total_slashing_balance // (
        total_balance // increment
    )
    for index, validator in enumerate(state.validators):
        if (
            validator.slashed
            and epoch + EPOCHS_PER_SLASHINGS_VECTOR // 2 == validator.withdrawable_epoch
        ):
            effective_balance_increments = validator.effective_balance // increment
            # [Modified in Electra:EIP7251]
            penalty = penalty_per_effective_balance_increment * effective_balance_increments
            decrease_balance(state, ValidatorIndex(index), penalty)
```

#### New `apply_pending_deposit`

```python
def apply_pending_deposit(state: BeaconState, deposit: PendingDeposit) -> None:
    """
    Applies ``deposit`` to the ``state``.
    """
    validator_pubkeys = [v.pubkey for v in state.validators]
    if deposit.pubkey not in validator_pubkeys:
        # Verify the deposit signature (proof of possession) which is not checked by the deposit contract
        if is_valid_deposit_signature(
            deposit.pubkey, deposit.withdrawal_credentials, deposit.amount, deposit.signature
        ):
            add_validator_to_registry(
                state, deposit.pubkey, deposit.withdrawal_credentials, deposit.amount
            )
    else:
        validator_index = ValidatorIndex(validator_pubkeys.index(deposit.pubkey))
        increase_balance(state, validator_index, deposit.amount)
```

#### New `process_pending_deposits`

Iterating over `pending_deposits` queue this function runs the following checks
before applying pending deposit:

1. All Eth1 bridge deposits are processed before the first deposit request gets
   processed.
2. Deposit position in the queue is finalized.
3. Deposit does not exceed the `MAX_PENDING_DEPOSITS_PER_EPOCH` limit.
4. Deposit does not exceed the activation churn limit.

```python
def process_pending_deposits(state: BeaconState) -> None:
    next_epoch = Epoch(get_current_epoch(state) + 1)
    available_for_processing = state.deposit_balance_to_consume + get_activation_exit_churn_limit(
        state
    )
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

        # Calculate the consolidated balance
        source_effective_balance = min(
            state.balances[pending_consolidation.source_index], source_validator.effective_balance
        )

        # Move active balance to target. Excess balance is withdrawable.
        decrease_balance(state, pending_consolidation.source_index, source_effective_balance)
        increase_balance(state, pending_consolidation.target_index, source_effective_balance)
        next_pending_consolidation += 1

    state.pending_consolidations = state.pending_consolidations[next_pending_consolidation:]
```

#### Modified `process_effective_balance_updates`

*Note*: The function `process_effective_balance_updates` is modified to use the
new limit for the maximum effective balance.

```python
def process_effective_balance_updates(state: BeaconState) -> None:
    # Update effective balances with hysteresis
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        HYSTERESIS_INCREMENT = uint64(EFFECTIVE_BALANCE_INCREMENT // HYSTERESIS_QUOTIENT)
        DOWNWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_DOWNWARD_MULTIPLIER
        UPWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_UPWARD_MULTIPLIER
        # [Modified in Electra:EIP7251]
        max_effective_balance = get_max_effective_balance(validator)

        if (
            balance + DOWNWARD_THRESHOLD < validator.effective_balance
            or validator.effective_balance + UPWARD_THRESHOLD < balance
        ):
            validator.effective_balance = min(
                balance - balance % EFFECTIVE_BALANCE_INCREMENT, max_effective_balance
            )
```

### Execution engine

#### Request data

##### Modified `NewPayloadRequest`

```python
@dataclass
class NewPayloadRequest(object):
    execution_payload: ExecutionPayload
    versioned_hashes: Sequence[VersionedHash]
    parent_beacon_block_root: Root
    # [New in Electra]
    execution_requests: ExecutionRequests
```

#### Engine APIs

##### Modified `is_valid_block_hash`

*Note*: The function `is_valid_block_hash` is modified to include the additional
`execution_requests_list`.

```python
def is_valid_block_hash(
    self: ExecutionEngine,
    execution_payload: ExecutionPayload,
    parent_beacon_block_root: Root,
    execution_requests_list: Sequence[bytes],
) -> bool:
    """
    Return ``True`` if and only if ``execution_payload.block_hash`` is computed correctly.
    """
    ...
```

##### Modified `notify_new_payload`

*Note*: The function `notify_new_payload` is modified to include the additional
`execution_requests_list`.

```python
def notify_new_payload(
    self: ExecutionEngine,
    execution_payload: ExecutionPayload,
    parent_beacon_block_root: Root,
    execution_requests_list: Sequence[bytes],
) -> bool:
    """
    Return ``True`` if and only if ``execution_payload`` and ``execution_requests_list``
    are valid with respect to ``self.execution_state``.
    """
    ...
```

##### Modified `verify_and_notify_new_payload`

*Note*: The function `verify_and_notify_new_payload` is modified to pass the
additional parameter `execution_requests_list` when calling
`is_valid_block_hash` and `notify_new_payload` in Electra.

```python
def verify_and_notify_new_payload(
    self: ExecutionEngine, new_payload_request: NewPayloadRequest
) -> bool:
    """
    Return ``True`` if and only if ``new_payload_request`` is valid with respect to ``self.execution_state``.
    """
    execution_payload = new_payload_request.execution_payload
    parent_beacon_block_root = new_payload_request.parent_beacon_block_root
    # [New in Electra]
    execution_requests_list = get_execution_requests_list(new_payload_request.execution_requests)

    if b"" in execution_payload.transactions:
        return False

    # [Modified in Electra]
    if not self.is_valid_block_hash(
        execution_payload, parent_beacon_block_root, execution_requests_list
    ):
        return False

    if not self.is_valid_versioned_hashes(new_payload_request):
        return False

    # [Modified in Electra]
    if not self.notify_new_payload(
        execution_payload, parent_beacon_block_root, execution_requests_list
    ):
        return False

    return True
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    # [Modified in Electra:EIP7251]
    process_withdrawals(state, block.body.execution_payload)
    # [Modified in Electra:EIP6110]
    process_execution_payload(state, block.body, EXECUTION_ENGINE)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    # [Modified in Electra:EIP6110:EIP7002:EIP7549:EIP7251]
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### Withdrawals

##### New `get_pending_partial_withdrawals`

```python
def get_pending_partial_withdrawals(
    state: BeaconState,
    withdrawal_index: WithdrawalIndex,
    epoch: Epoch,
    prior_withdrawals: Sequence[Withdrawal],
) -> Tuple[Sequence[Withdrawal], WithdrawalIndex, uint64]:
    withdrawals: List[Withdrawal] = []
    processed_count = 0
    bound = min(
        len(prior_withdrawals) + MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP,
        MAX_WITHDRAWALS_PER_PAYLOAD - 1,
    )

    for withdrawal in state.pending_partial_withdrawals:
        all_withdrawals = prior_withdrawals + withdrawals
        is_not_withdrawable = withdrawal.withdrawable_epoch > epoch
        has_reached_bound = len(all_withdrawals) == bound
        if is_not_withdrawable or has_reached_bound:
            break

        validator_index = withdrawal.validator_index
        validator = state.validators[validator_index]
        balance = get_balance_minus_withdrawals(state, validator_index, all_withdrawals)
        if is_eligible_for_partial_withdrawals(validator, balance):
            withdrawal_amount = min(balance - MIN_ACTIVATION_BALANCE, withdrawal.amount)
            withdrawals.append(
                Withdrawal(
                    index=withdrawal_index,
                    validator_index=validator_index,
                    address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                    amount=withdrawal_amount,
                )
            )
            withdrawal_index += WithdrawalIndex(1)

        processed_count += 1

    return withdrawals, withdrawal_index, processed_count
```

##### Modified `get_sweep_withdrawals`

*Note*: The function `get_sweep_withdrawals` is modified to use
`get_max_effective_balance`.

```python
def get_sweep_withdrawals(
    state: BeaconState,
    withdrawal_index: WithdrawalIndex,
    validator_index: ValidatorIndex,
    epoch: Epoch,
    prior_withdrawals: Sequence[Withdrawal],
) -> Sequence[Withdrawal]:
    withdrawals: List[Withdrawal] = []
    bound = min(len(state.validators), MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)

    for _ in range(bound):
        all_withdrawals = prior_withdrawals + withdrawals
        if len(all_withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
            break

        validator = state.validators[validator_index]
        balance = get_balance_minus_withdrawals(state, validator_index, all_withdrawals)
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
                    # [Modified in Electra:EIP7251]
                    amount=balance - get_max_effective_balance(validator),
                )
            )
            withdrawal_index += WithdrawalIndex(1)

        validator_index = ValidatorIndex((validator_index + 1) % len(state.validators))

    return withdrawals
```

##### Modified `get_expected_withdrawals`

*Note*: The function `get_expected_withdrawals` is modified to support EIP7251.

```python
def get_expected_withdrawals(state: BeaconState) -> Tuple[Sequence[Withdrawal], uint64]:
    epoch = get_current_epoch(state)
    withdrawal_index = state.next_withdrawal_index
    validator_index = state.next_withdrawal_validator_index
    withdrawals: List[Withdrawal] = []

    # [New in Electra:EIP7251]
    # Get partial withdrawals
    partial_withdrawals, withdrawal_index, processed_partial_withdrawals_count = (
        get_pending_partial_withdrawals(state, withdrawal_index, epoch, withdrawals)
    )
    withdrawals.extend(partial_withdrawals)

    # Get sweep withdrawals
    sweep_withdrawals = get_sweep_withdrawals(
        state, withdrawal_index, validator_index, epoch, withdrawals
    )
    withdrawals.extend(sweep_withdrawals)

    # [Modified in Electra:EIP7251]
    return withdrawals, processed_partial_withdrawals_count
```

##### Modified `process_withdrawals`

*Note*: The function `process_withdrawals` is modified to support EIP7251.

```python
def process_withdrawals(state: BeaconState, payload: ExecutionPayload) -> None:
    # [Modified in Electra:EIP7251]
    expected_withdrawals, processed_partial_withdrawals_count = get_expected_withdrawals(state)

    assert payload.withdrawals == expected_withdrawals

    for withdrawal in expected_withdrawals:
        decrease_balance(state, withdrawal.validator_index, withdrawal.amount)

    # [New in Electra:EIP7251]
    # Update pending partial withdrawals
    state.pending_partial_withdrawals = state.pending_partial_withdrawals[
        processed_partial_withdrawals_count:
    ]

    # Update the next withdrawal index if this block contained withdrawals
    if len(expected_withdrawals) != 0:
        latest_withdrawal = expected_withdrawals[-1]
        state.next_withdrawal_index = WithdrawalIndex(latest_withdrawal.index + 1)

    # Update the next validator index to start the next withdrawal sweep
    if len(expected_withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
        # Next sweep starts after the latest withdrawal's validator index
        next_validator_index = ValidatorIndex(
            (expected_withdrawals[-1].validator_index + 1) % len(state.validators)
        )
        state.next_withdrawal_validator_index = next_validator_index
    else:
        # Advance sweep by the max length of the sweep if there was not a full set of withdrawals
        next_index = state.next_withdrawal_validator_index + MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
        next_validator_index = ValidatorIndex(next_index % len(state.validators))
        state.next_withdrawal_validator_index = next_validator_index
```

#### Execution payload

##### New `get_execution_requests_list`

*Note*: Encodes execution requests as defined by
[EIP-7685](https://eips.ethereum.org/EIPS/eip-7685).

```python
def get_execution_requests_list(execution_requests: ExecutionRequests) -> Sequence[bytes]:
    requests = [
        (DEPOSIT_REQUEST_TYPE, execution_requests.deposits),
        (WITHDRAWAL_REQUEST_TYPE, execution_requests.withdrawals),
        (CONSOLIDATION_REQUEST_TYPE, execution_requests.consolidations),
    ]

    return [
        request_type + ssz_serialize(request_data)
        for request_type, request_data in requests
        if len(request_data) != 0
    ]
```

##### Modified `process_execution_payload`

*Note*: The function `process_execution_payload` is modified to pass
`execution_requests` into `execution_engine.verify_and_notify_new_payload` (via
the updated `NewPayloadRequest`).

```python
def process_execution_payload(
    state: BeaconState, body: BeaconBlockBody, execution_engine: ExecutionEngine
) -> None:
    payload = body.execution_payload

    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_time_at_slot(state, state.slot)
    # [Modified in Electra:EIP7691]
    # Verify commitments are under limit
    assert len(body.blob_kzg_commitments) <= MAX_BLOBS_PER_BLOCK_ELECTRA

    # Compute list of versioned hashes
    versioned_hashes = [
        kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments
    ]

    # Verify the execution payload is valid
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
            # [New in Electra]
            execution_requests=body.execution_requests,
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
    )
```

#### Operations

##### Modified `process_operations`

*Note*: The function `process_operations` is modified to support all of the new
functionality in Electra.

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # [Modified in Electra:EIP6110]
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

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    # [Modified in Electra:EIP7549]
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    # [Modified in Electra:EIP7251]
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    # [New in Electra:EIP6110]
    for_ops(body.execution_requests.deposits, process_deposit_request)
    # [New in Electra:EIP7002:EIP7251]
    for_ops(body.execution_requests.withdrawals, process_withdrawal_request)
    # [New in Electra:EIP7251]
    for_ops(body.execution_requests.consolidations, process_consolidation_request)
```

##### Attestations

###### Modified `process_attestation`

*Note*: The function is modified to support EIP7549.

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.target.epoch == compute_epoch_at_slot(data.slot)
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot

    # [Modified in Electra:EIP7549]
    assert data.index == 0
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
    if data.target.epoch == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation

    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, attestation):
        for flag_index, weight in enumerate(PARTICIPATION_FLAG_WEIGHTS):
            if flag_index in participation_flag_indices and not has_flag(
                epoch_participation[index], flag_index
            ):
                epoch_participation[index] = add_flag(epoch_participation[index], flag_index)
                proposer_reward_numerator += get_base_reward(state, index) * weight

    # Reward proposer
    proposer_reward_denominator = (
        (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT) * WEIGHT_DENOMINATOR // PROPOSER_WEIGHT
    )
    proposer_reward = Gwei(proposer_reward_numerator // proposer_reward_denominator)
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
```

##### Deposits

###### Modified `get_validator_from_deposit`

*Note*: The function is modified to use `MAX_EFFECTIVE_BALANCE_ELECTRA` for
compounding withdrawal credential.

```python
def get_validator_from_deposit(
    pubkey: BLSPubkey, withdrawal_credentials: Bytes32, amount: uint64
) -> Validator:
    validator = Validator(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        effective_balance=Gwei(0),
        slashed=False,
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
    )

    # [Modified in Electra:EIP7251]
    max_effective_balance = get_max_effective_balance(validator)
    validator.effective_balance = min(
        amount - amount % EFFECTIVE_BALANCE_INCREMENT, max_effective_balance
    )

    return validator
```

###### Modified `add_validator_to_registry`

*Note*: The function `add_validator_to_registry` is modified to use the modified
`get_validator_from_deposit`.

```python
def add_validator_to_registry(
    state: BeaconState, pubkey: BLSPubkey, withdrawal_credentials: Bytes32, amount: uint64
) -> None:
    index = get_index_for_new_validator(state)
    # [Modified in Electra:EIP7251]
    validator = get_validator_from_deposit(pubkey, withdrawal_credentials, amount)
    set_or_append_list(state.validators, index, validator)
    set_or_append_list(state.balances, index, amount)
    set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.inactivity_scores, index, uint64(0))
```

###### Modified `apply_deposit`

*Note*: The function `apply_deposit` is modified to support EIP7251.

```python
def apply_deposit(
    state: BeaconState,
    pubkey: BLSPubkey,
    withdrawal_credentials: Bytes32,
    amount: uint64,
    signature: BLSSignature,
) -> None:
    validator_pubkeys = [v.pubkey for v in state.validators]
    if pubkey not in validator_pubkeys:
        # Verify the deposit signature (proof of possession) which is not checked by the deposit contract
        if is_valid_deposit_signature(pubkey, withdrawal_credentials, amount, signature):
            # [Modified in Electra:EIP7251]
            add_validator_to_registry(state, pubkey, withdrawal_credentials, Gwei(0))
        else:
            return

    # [Modified in Electra:EIP7251]
    # Increase balance by deposit amount
    state.pending_deposits.append(
        PendingDeposit(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            amount=amount,
            signature=signature,
            slot=GENESIS_SLOT,  # Use GENESIS_SLOT to distinguish from a pending deposit request
        )
    )
```

###### New `is_valid_deposit_signature`

```python
def is_valid_deposit_signature(
    pubkey: BLSPubkey, withdrawal_credentials: Bytes32, amount: uint64, signature: BLSSignature
) -> bool:
    deposit_message = DepositMessage(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
    )
    # Fork-agnostic domain since deposits are valid across forks
    domain = compute_domain(DOMAIN_DEPOSIT)
    signing_root = compute_signing_root(deposit_message, domain)
    return bls.Verify(pubkey, signing_root, signature)
```

###### Modified `process_deposit`

*Note*: The function `process_deposit` is modified to use the modified
`apply_deposit`.

```python
def process_deposit(state: BeaconState, deposit: Deposit) -> None:
    # Verify the Merkle branch
    assert is_valid_merkle_branch(
        leaf=hash_tree_root(deposit.data),
        branch=deposit.proof,
        # Add 1 for the List length mix-in
        depth=DEPOSIT_CONTRACT_TREE_DEPTH + 1,
        index=state.eth1_deposit_index,
        root=state.eth1_data.deposit_root,
    )

    # Deposits must be processed in order
    state.eth1_deposit_index += 1

    # [Modified in Electra:EIP7251]
    apply_deposit(
        state=state,
        pubkey=deposit.data.pubkey,
        withdrawal_credentials=deposit.data.withdrawal_credentials,
        amount=deposit.data.amount,
        signature=deposit.data.signature,
    )
```

##### Voluntary exits

###### Modified `process_voluntary_exit`

*Note*: The function `process_voluntary_exit` is modified to ensure the
validator has no pending withdrawals in the queue.

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
    # [New in Electra:EIP7251]
    # Only exit validator if it has no pending withdrawals in the queue
    assert get_pending_balance_to_withdraw(state, voluntary_exit.validator_index) == 0
    # Verify signature
    domain = compute_domain(
        DOMAIN_VOLUNTARY_EXIT, CAPELLA_FORK_VERSION, state.genesis_validators_root
    )
    signing_root = compute_signing_root(voluntary_exit, domain)
    assert bls.Verify(validator.pubkey, signing_root, signed_voluntary_exit.signature)
    # Initiate exit
    initiate_validator_exit(state, voluntary_exit.validator_index)
```

##### Execution layer withdrawal requests

###### New `process_withdrawal_request`

```python
def process_withdrawal_request(state: BeaconState, withdrawal_request: WithdrawalRequest) -> None:
    amount = withdrawal_request.amount
    is_full_exit_request = amount == FULL_EXIT_REQUEST_AMOUNT

    # If partial withdrawal queue is full, only full exits are processed
    if (
        len(state.pending_partial_withdrawals) == PENDING_PARTIAL_WITHDRAWALS_LIMIT
        and not is_full_exit_request
    ):
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
    has_excess_balance = (
        state.balances[index] > MIN_ACTIVATION_BALANCE + pending_balance_to_withdraw
    )

    # Only allow partial withdrawals with compounding withdrawal credentials
    if (
        has_compounding_withdrawal_credential(validator)
        and has_sufficient_effective_balance
        and has_excess_balance
    ):
        to_withdraw = min(
            state.balances[index] - MIN_ACTIVATION_BALANCE - pending_balance_to_withdraw, amount
        )
        exit_queue_epoch = compute_exit_epoch_and_update_churn(state, to_withdraw)
        withdrawable_epoch = Epoch(exit_queue_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY)
        state.pending_partial_withdrawals.append(
            PendingPartialWithdrawal(
                validator_index=index,
                amount=to_withdraw,
                withdrawable_epoch=withdrawable_epoch,
            )
        )
```

##### Deposit requests

###### New `process_deposit_request`

```python
def process_deposit_request(state: BeaconState, deposit_request: DepositRequest) -> None:
    # Set deposit request start index
    if state.deposit_requests_start_index == UNSET_DEPOSIT_REQUESTS_START_INDEX:
        state.deposit_requests_start_index = deposit_request.index

    # Create pending deposit
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

##### Execution layer consolidation requests

###### New `is_valid_switch_to_compounding_request`

```python
def is_valid_switch_to_compounding_request(
    state: BeaconState, consolidation_request: ConsolidationRequest
) -> bool:
    # Switch to compounding requires source and target be equal
    if consolidation_request.source_pubkey != consolidation_request.target_pubkey:
        return False

    # Verify pubkey exists
    source_pubkey = consolidation_request.source_pubkey
    validator_pubkeys = [v.pubkey for v in state.validators]
    if source_pubkey not in validator_pubkeys:
        return False

    source_validator = state.validators[ValidatorIndex(validator_pubkeys.index(source_pubkey))]

    # Verify request has been authorized
    if source_validator.withdrawal_credentials[12:] != consolidation_request.source_address:
        return False

    # Verify source withdrawal credentials
    if not has_eth1_withdrawal_credential(source_validator):
        return False

    # Verify the source is active
    current_epoch = get_current_epoch(state)
    if not is_active_validator(source_validator, current_epoch):
        return False

    # Verify exit for source has not been initiated
    if source_validator.exit_epoch != FAR_FUTURE_EPOCH:
        return False

    return True
```

###### New `process_consolidation_request`

```python
def process_consolidation_request(
    state: BeaconState, consolidation_request: ConsolidationRequest
) -> None:
    if is_valid_switch_to_compounding_request(state, consolidation_request):
        validator_pubkeys = [v.pubkey for v in state.validators]
        request_source_pubkey = consolidation_request.source_pubkey
        source_index = ValidatorIndex(validator_pubkeys.index(request_source_pubkey))
        switch_to_compounding_validator(state, source_index)
        return

    # Verify that source != target, so a consolidation cannot be used as an exit
    if consolidation_request.source_pubkey == consolidation_request.target_pubkey:
        return
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

    # Verify source withdrawal credentials
    has_correct_credential = has_execution_withdrawal_credential(source_validator)
    is_correct_source_address = (
        source_validator.withdrawal_credentials[12:] == consolidation_request.source_address
    )
    if not (has_correct_credential and is_correct_source_address):
        return

    # Verify that target has compounding withdrawal credentials
    if not has_compounding_withdrawal_credential(target_validator):
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
    # Verify the source has been active long enough
    if current_epoch < source_validator.activation_epoch + SHARD_COMMITTEE_PERIOD:
        return
    # Verify the source has no pending withdrawals in the queue
    if get_pending_balance_to_withdraw(state, source_index) > 0:
        return

    # Initiate source validator exit and append pending consolidation
    source_validator.exit_epoch = compute_consolidation_epoch_and_update_churn(
        state, source_validator.effective_balance
    )
    source_validator.withdrawable_epoch = Epoch(
        source_validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    state.pending_consolidations.append(
        PendingConsolidation(source_index=source_index, target_index=target_index)
    )
```
