# EIP7251 - Spec

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Withdrawal prefixes](#withdrawal-prefixes)
  - [Domains](#domains)
- [Presets](#presets)
  - [Gwei values](#gwei-values)
  - [Rewards and penalties](#rewards-and-penalties)
  - [Max operations per block](#max-operations-per-block)
  - [Execution](#execution)
  - [State list lengths](#state-list-lengths)
- [Configuration](#configuration)
  - [Validator cycle](#validator-cycle)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [New `PendingBalanceDeposit`](#new-pendingbalancedeposit)
    - [New `PartialWithdrawal`](#new-partialwithdrawal)
    - [New `ExecutionLayerWithdrawRequest`](#new-executionlayerwithdrawrequest)
    - [New `Consolidation`](#new-consolidation)
    - [New `SignedConsolidation`](#new-signedconsolidation)
    - [New `PendingConsolidation`](#new-pendingconsolidation)
  - [Extended Containers](#extended-containers)
    - [`BeaconState`](#beaconstate)
    - [`BeaconBlockBody`](#beaconblockbody)
- [Helpers](#helpers)
  - [Predicates](#predicates)
    - [Updated `is_eligible_for_activation_queue`](#updated-is_eligible_for_activation_queue)
    - [New `is_compounding_withdrawal_credential`](#new-is_compounding_withdrawal_credential)
    - [New `has_compounding_withdrawal_credential`](#new-has_compounding_withdrawal_credential)
    - [New `has_execution_withdrawal_credential`](#new-has_execution_withdrawal_credential)
    - [Updated `is_fully_withdrawable_validator`](#updated-is_fully_withdrawable_validator)
    - [Updated `is_partially_withdrawable_validator`](#updated-is_partially_withdrawable_validator)
  - [Beacon state accessors](#beacon-state-accessors)
    - [New `get_validator_max_effective_balance`](#new-get_validator_max_effective_balance)
    - [New `get_churn_limit`](#new-get_churn_limit)
    - [New `get_activation_exit_churn_limit`](#new-get_activation_exit_churn_limit)
    - [New `get_consolidation_churn_limit`](#new-get_consolidation_churn_limit)
    - [New `get_active_balance`](#new-get_active_balance)
  - [Beacon state mutators](#beacon-state-mutators)
    - [Updated  `initiate_validator_exit`](#updated--initiate_validator_exit)
    - [New `set_compounding_withdrawal_credentials`](#new-set_compounding_withdrawal_credentials)
    - [New `switch_to_compounding_validator`](#new-switch_to_compounding_validator)
    - [New `queue_excess_active_balance`](#new-queue_excess_active_balance)
    - [New `compute_exit_epoch_and_update_churn`](#new-compute_exit_epoch_and_update_churn)
    - [New `compute_consolidation_epoch_and_update_churn`](#new-compute_consolidation_epoch_and_update_churn)
    - [Updated `slash_validator`](#updated-slash_validator)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Updated `process_epoch`](#updated-process_epoch)
    - [Updated  `process_registry_updates`](#updated--process_registry_updates)
    - [New `process_pending_balance_deposits`](#new-process_pending_balance_deposits)
    - [New `process_pending_consolidations`](#new-process_pending_consolidations)
    - [Updated `process_effective_balance_updates`](#updated-process_effective_balance_updates)
  - [Block processing](#block-processing)
      - [Updated `get_expected_withdrawals`](#updated-get_expected_withdrawals)
      - [Updated `process_withdrawals`](#updated-process_withdrawals)
    - [Operations](#operations)
      - [Updated `process_operations`](#updated-process_operations)
      - [Deposits](#deposits)
        - [Updated  `apply_deposit`](#updated--apply_deposit)
        - [New `is_valid_deposit_signature`](#new-is_valid_deposit_signature)
        - [Modified `add_validator_to_registry`](#modified-add_validator_to_registry)
        - [Updated `get_validator_from_deposit`](#updated-get_validator_from_deposit)
      - [Withdrawals](#withdrawals)
        - [New `process_execution_layer_withdraw_request`](#new-process_execution_layer_withdraw_request)
      - [Consolidations](#consolidations)
        - [New `process_consolidation`](#new-process_consolidation)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

See [a modest proposal](https://notes.ethereum.org/@mikeneuder/increase-maxeb), the [diff view](https://github.com/michaelneuder/consensus-specs/pull/3/files) and 
[security considerations](https://notes.ethereum.org/@fradamt/meb-increase-security).

*Note:* This specification is built upon [Deneb](../../deneb/beacon-chain.md).

## Constants

The following values are (non-configurable) constants used throughout the specification.

### Withdrawal prefixes

| Name | Value |
| - | - |
| `BLS_WITHDRAWAL_PREFIX` | `Bytes1('0x00')` |
| `ETH1_ADDRESS_WITHDRAWAL_PREFIX` | `Bytes1('0x01')` |
| `COMPOUNDING_WITHDRAWAL_PREFIX` | `Bytes1('0x02')` |

### Domains

| Name | Value |
| - | - |
| `DOMAIN_CONSOLIDATION` | `DomainType('0x0B000000')` |

## Presets

### Gwei values

| Name | Value |
| - | - |
| `MIN_ACTIVATION_BALANCE` | `Gwei(2**5 * 10**9)`  (= 32,000,000,000) |
| `MAX_EFFECTIVE_BALANCE_EIP7251` | `Gwei(2**11 * 10**9)` (= 2048,000,000,000) |

### Rewards and penalties

| Name | Value |
| - | - |
| `MIN_SLASHING_PENALTY_QUOTIENT_EIP7251` | `uint64(2**12)`  (= 4,096) |
| `WHISTLEBLOWER_REWARD_QUOTIENT_EIP7251` | `uint64(2**12)`  (= 4,096) |

### Max operations per block

| Name | Value |
| - | - |
| `MAX_CONSOLIDATIONS` | `uint64(1)` |

### Execution

| Name | Value | Description |
| - | - | - |
| `MAX_PARTIAL_WITHDRAWALS_PER_PAYLOAD` | `uint64(2**3)` (= 8) | Maximum amount of partial withdrawals allowed in each payload |

### State list lengths

| Name | Value | Unit |
| - | - | :-: |
| `PENDING_BALANCE_DEPOSITS_LIMIT` | `uint64(2**27)` (= 134,217,728) | pending balance deposits |
| `PENDING_PARTIAL_WITHDRAWALS_LIMIT` | `uint64(2**27)` (= 134,217,728) | pending partial withdrawals |
| `PENDING_CONSOLIDATIONS_LIMIT` | `uint64(2**18)` (= 262,144) | pending consolidations |


## Configuration

### Validator cycle

| Name | Value |
| - | - |
| `MIN_PER_EPOCH_CHURN_LIMIT_EIP7251` | `Gwei(2**7 * 10**9)` (= 128,000,000,000) | # Equivalent to 4 32 ETH validators
| `MAX_PER_EPOCH_ACTIVATION_EXIT_CHURN_LIMIT` | `Gwei(2**8 * 10**9)` (256,000,000,000) |


## Containers

### New containers

#### New `PendingBalanceDeposit`

```python
class PendingBalanceDeposit(Container):
    index: ValidatorIndex
    amount: Gwei
```

#### New `PartialWithdrawal`

```python
class PartialWithdrawal(Container):
    index: ValidatorIndex
    amount: Gwei
    withdrawable_epoch: Epoch
```
#### New `ExecutionLayerWithdrawRequest`

```python
class ExecutionLayerWithdrawRequest(Container):
    source_address: ExecutionAddress
    validator_pubkey: BLSPubkey
    amount: Gwei
```

#### New `Consolidation`

```python
class Consolidation(Container):
    source_index: ValidatorIndex
    target_index: ValidatorIndex
    epoch: Epoch
```

#### New `SignedConsolidation`
```python
class SignedConsolidation(Container):
    message: Consolidation
    signature: BLSSignature
```

#### New `PendingConsolidation`
```python
class PendingConsolidation(Container):
    source_index: ValidatorIndex
    target_index: ValidatorIndex
```

### Extended Containers

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
    latest_execution_payload_header: ExecutionPayloadHeader
    # Withdrawals
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    # Deep history valid from Capella onwards
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
    # EIP-7251
    deposit_balance_to_consume: Gwei  # [New in EIP-7251]
    exit_balance_to_consume: Gwei  # [New in EIP-7251]
    earliest_exit_epoch: Epoch  # [New in EIP-7251]
    consolidation_balance_to_consume: Gwei  # [New in EIP-7251]
    earliest_consolidation_epoch: Epoch  # [New in EIP-7251]
    pending_balance_deposits: List[PendingBalanceDeposit, PENDING_BALANCE_DEPOSITS_LIMIT]  # [New in EIP-7251]
    pending_partial_withdrawals: List[PartialWithdrawal, PENDING_PARTIAL_WITHDRAWALS_LIMIT]  # [New in EIP-7251]
    pending_consolidations: List[PendingConsolidation, PENDING_CONSOLIDATIONS_LIMIT]  # [New in EIP-7251]
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data  # Eth1 data vote
    graffiti: Bytes32  # Arbitrary data
    # Operations
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    # Execution
    execution_payload: ExecutionPayload 
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    consolidations: List[SignedConsolidation, MAX_CONSOLIDATIONS]  # [New in EIP-7251]
```

## Helpers

### Predicates

#### Updated `is_eligible_for_activation_queue`

```python
def is_eligible_for_activation_queue(validator: Validator) -> bool:
    """
    Check if ``validator`` is eligible to be placed into the activation queue.
    """
    return (
        validator.activation_eligibility_epoch == FAR_FUTURE_EPOCH
        and validator.effective_balance >= MIN_ACTIVATION_BALANCE  # [Modified in EIP7251]
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

#### Updated `is_fully_withdrawable_validator`

```python
def is_fully_withdrawable_validator(validator: Validator, balance: Gwei, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is fully withdrawable.
    """
    return (
        has_execution_withdrawal_credential(validator)  # [Modified in EIP7251]
        and validator.withdrawable_epoch <= epoch
        and balance > 0
    )
```

#### Updated `is_partially_withdrawable_validator`

```python
def is_partially_withdrawable_validator(validator: Validator, balance: Gwei) -> bool:
    """
    Check if ``validator`` is partially withdrawable.
    """
    max_effective_balance = get_validator_max_effective_balance(validator)
    has_max_effective_balance = validator.effective_balance == max_effective_balance  # [Modified in EIP7251]
    has_excess_balance = balance > max_effective_balance  # [Modified in EIP7251]
    return (
        has_execution_withdrawal_credential(validator)  # [Modified in EIP7251]
        and has_max_effective_balance
        and has_excess_balance
    )
```

### Beacon state accessors

#### New `get_validator_max_effective_balance`

```python
def get_validator_max_effective_balance(validator: Validator) -> Gwei:
    """
    Get max effective balance for ``validator``.
    """
    if has_compounding_withdrawal_credential(validator):
        return MAX_EFFECTIVE_BALANCE_EIP7251
    else:
        return MIN_ACTIVATION_BALANCE
```

#### New `get_churn_limit`

```python
def get_churn_limit(state: BeaconState) -> Gwei:
    """
    Return the churn limit for the current epoch.
    """
    churn = max(
        MIN_PER_EPOCH_CHURN_LIMIT_EIP7251, 
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
    return min(MAX_PER_EPOCH_ACTIVATION_EXIT_CHURN_LIMIT, get_churn_limit(state))
```

#### New `get_consolidation_churn_limit`

```python
def get_consolidation_churn_limit(state: BeaconState) -> Gwei:
    return get_churn_limit(state) - get_activation_exit_churn_limit(state)
```

#### New `get_active_balance`

```python
def get_active_balance(state: BeaconState, validator_index: ValidatorIndex) -> Gwei:
    active_balance_ceil = (
        MIN_ACTIVATION_BALANCE 
        if has_eth1_withdrawal_credential(state.validators[validator_index]) 
        else MAX_EFFECTIVE_BALANCE_EIP7251
    )
    return min(state.balances[validator_index], active_balance_ceil)
```

### Beacon state mutators

#### Updated  `initiate_validator_exit`

```python
def initiate_validator_exit(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Initiate the exit of the validator with index ``index``.
    """
    # Return if validator already initiated exit
    validator = state.validators[index]
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return

    # Compute exit queue epoch [Modified in EIP 7251]
    exit_queue_epoch = compute_exit_epoch_and_update_churn(state, validator.effective_balance)

    # Set validator exit epoch and withdrawable epoch
    validator.exit_epoch = exit_queue_epoch
    validator.withdrawable_epoch = Epoch(validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY)
```

#### New `set_compounding_withdrawal_credentials`

```python
def set_compounding_withdrawal_credentials(state: BeaconState, index: ValidatorIndex) -> None:
    validator = state.validators[index]
    if has_eth1_withdrawal_credential(validator):
        validator.withdrawal_credentials[:1] = COMPOUNDING_WITHDRAWAL_PREFIX
```

#### New `switch_to_compounding_validator`

```python
def switch_to_compounding_validator(state: BeaconState, index: ValidatorIndex) -> None:
    validator = state.validators[index]
    if has_eth1_withdrawal_credential(validator):
        validator.withdrawal_credentials[:1] = COMPOUNDING_WITHDRAWAL_PREFIX
        queue_excess_active_balance(state, index)
```

#### New `queue_excess_active_balance`

```python
def queue_excess_active_balance(state: BeaconState, index: ValidatorIndex) -> None:
    balance = state.balances[index]
    if balance > MAX_EFFECTIVE_BALANCE:
        excess_balance = balance - MAX_EFFECTIVE_BALANCE
        state.balances[index] = balance - excess_balance
        state.pending_balance_deposits.append(
            PendingBalanceDeposit(index=index, amount=excess_balance)
        )
```

#### New `compute_exit_epoch_and_update_churn`


```python
def compute_exit_epoch_and_update_churn(state: BeaconState, exit_balance: Gwei) -> Epoch:
    earliest_exit_epoch = compute_activation_exit_epoch(get_current_epoch(state))
    per_epoch_churn = get_activation_exit_churn_limit(state)
    # New epoch for exits.
    if state.earliest_exit_epoch < earliest_exit_epoch:
        state.earliest_exit_epoch = earliest_exit_epoch
        state.exit_balance_to_consume = per_epoch_churn

    if exit_balance <= state.exit_balance_to_consume:
        # Exit fits in the current earliest epoch.
        state.exit_balance_to_consume -= exit_balance
    else:
        # Exit doesn't fit in the current earliest epoch.
        balance_to_process = exit_balance - state.exit_balance_to_consume
        additional_epochs, remainder = divmod(balance_to_process, per_epoch_churn)
        state.earliest_exit_epoch += additional_epochs + 1
        state.exit_balance_to_consume = per_epoch_churn - remainder

    return state.earliest_exit_epoch
```

#### New `compute_consolidation_epoch_and_update_churn`

```python
def compute_consolidation_epoch_and_update_churn(state: BeaconState, consolidation_balance: Gwei) -> Epoch:
    earliest_consolidation_epoch = compute_activation_exit_epoch(get_current_epoch(state))
    per_epoch_consolidation_churn = get_consolidation_churn_limit(state)
    # New epoch for consolidations.
    if state.earliest_consolidation_epoch < earliest_consolidation_epoch:
        state.earliest_consolidation_epoch = earliest_consolidation_epoch
        state.consolidation_balance_to_consume = per_epoch_consolidation_churn

    if consolidation_balance <= state.consolidation_balance_to_consume:
        # Consolidation fits in the current earliest consolidation epoch.
        state.consolidation_balance_to_consume -= consolidation_balance
    else:
        # Consolidation doesn't fit in the current earliest epoch.
        balance_to_process = consolidation_balance - state.consolidation_balance_to_consume
        additional_epochs, remainder = divmod(balance_to_process, per_epoch_consolidation_churn)
        state.earliest_consolidation_epoch += additional_epochs + 1
        state.consolidation_balance_to_consume = per_epoch_consolidation_churn - remainder

    return state.earliest_consolidation_epoch
```

#### Updated `slash_validator`

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
    slashing_penalty = validator.effective_balance // MIN_SLASHING_PENALTY_QUOTIENT_EIP7251  # [Modified in EIP7251]
    decrease_balance(state, slashed_index, slashing_penalty)

    # Apply proposer and whistleblower rewards
    proposer_index = get_beacon_proposer_index(state)
    if whistleblower_index is None:
        whistleblower_index = proposer_index
    whistleblower_reward = Gwei(
        validator.effective_balance // WHISTLEBLOWER_REWARD_QUOTIENT_EIP7251)  # [Modified in EIP7251]
    proposer_reward = Gwei(whistleblower_reward * PROPOSER_WEIGHT // WEIGHT_DENOMINATOR)
    increase_balance(state, proposer_index, proposer_reward)
    increase_balance(state, whistleblower_index, Gwei(whistleblower_reward - proposer_reward))
```

## Beacon chain state transition function

### Epoch processing

#### Updated `process_epoch`
```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)  # [Modified in EIP7251]
    process_slashings(state)
    process_eth1_data_reset(state)
    process_pending_balance_deposits(state)  # New in EIP7251
    process_pending_consolidations(state)  # New in EIP7251
    process_effective_balance_updates(state)  # [Modified in EIP7251]
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
```

#### Updated  `process_registry_updates`

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
    available_for_processing = state.deposit_balance_to_consume + get_activation_exit_churn_limit(state)
    processed_amount = 0
    next_deposit_index = 0

    for deposit in state.pending_balance_deposits:
        if processed_amount + deposit.amount > available_for_processing:
            break
        increase_balance(state, deposit.index, deposit.amount)
        processed_amount += deposit.amount
        next_deposit_index += 1

    state.pending_balance_deposits = state.pending_balance_deposits[next_deposit_index:]

    if len(state.pending_balance_deposits) == 0:
        state.deposit_balance_to_consume = 0
    else:
        state.deposit_balance_to_consume = available_for_processing - processed_amount
```

#### New `process_pending_consolidations`

```python
def process_pending_consolidations(state: BeaconState) -> None:
    next_pending_consolidation = 0
    for pending_consolidation in state.pending_consolidations:
        source_validator = state.validators[pending_consolidation.source_index]
        if source_validator.slashed:
            next_pending_consolidation += 1
            continue
        if source_validator.withdrawable_epoch > get_current_epoch(state):
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

#### Updated `process_effective_balance_updates`

```python
def process_effective_balance_updates(state: BeaconState) -> None:
    # Update effective balances with hysteresis
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        HYSTERESIS_INCREMENT = uint64(EFFECTIVE_BALANCE_INCREMENT // HYSTERESIS_QUOTIENT)
        DOWNWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_DOWNWARD_MULTIPLIER
        UPWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_UPWARD_MULTIPLIER
        EFFECTIVE_BALANCE_LIMIT = (
            MAX_EFFECTIVE_BALANCE_EIP7251 if has_compounding_withdrawal_credential(validator)
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
    process_withdrawals(state, block.body.execution_payload)  # [Modified in EIP7251]
    process_execution_payload(state, block.body, EXECUTION_ENGINE)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)  # [Modified in EIP7251]
    process_sync_aggregate(state, block.body.sync_aggregate)
```

##### Updated `get_expected_withdrawals`

```python
def get_expected_withdrawals(state: BeaconState) -> Tuple[Sequence[Withdrawal], uint64]:
    epoch = get_current_epoch(state)
    withdrawal_index = state.next_withdrawal_index
    validator_index = state.next_withdrawal_validator_index
    withdrawals: List[Withdrawal] = []

    # [New in EIP7251] Consume pending partial withdrawals
    for withdrawal in state.pending_partial_withdrawals:
        if withdrawal.withdrawable_epoch > epoch or len(withdrawals) == MAX_PARTIAL_WITHDRAWALS_PER_PAYLOAD:
            break

        validator = state.validators[withdrawal.index]
        if validator.exit_epoch == FAR_FUTURE_EPOCH and state.balances[withdrawal.index] > MIN_ACTIVATION_BALANCE:
            withdrawable_balance = min(state.balances[withdrawal.index] - MIN_ACTIVATION_BALANCE, withdrawal.amount)
            withdrawals.append(Withdrawal(
                index=withdrawal_index,
                validator_index=withdrawal.index,
                address=ExecutionAddress(validator.withdrawal_credentials[12:]),
                amount=withdrawable_balance,
            ))
            withdrawal_index += WithdrawalIndex(1)

    partial_withdrawals_count = len(withdrawals)
    # END: Consume pending partial withdrawals

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
                amount=balance - get_validator_max_effective_balance(validator),  # [Modified in EIP7251]
            ))
            withdrawal_index += WithdrawalIndex(1)
        if len(withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
            break
        validator_index = ValidatorIndex((validator_index + 1) % len(state.validators))
    return withdrawals, partial_withdrawals_count
```

##### Updated `process_withdrawals`

```python
def process_withdrawals(state: BeaconState, payload: ExecutionPayload) -> None:
    expected_withdrawals, partial_withdrawals_count = get_expected_withdrawals(state)  # [Modified in EIP7251]

    assert len(payload.withdrawals) == len(expected_withdrawals)

    for expected_withdrawal, withdrawal in zip(expected_withdrawals, payload.withdrawals):
        assert withdrawal == expected_withdrawal
        decrease_balance(state, withdrawal.validator_index, withdrawal.amount)

    # [New in EIP7251] update pending partial withdrawals
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

#### Operations 

##### Updated `process_operations`

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # Verify that outstanding deposits are processed up to the maximum number of deposits
    assert len(body.deposits) == min(MAX_DEPOSITS, state.eth1_data.deposit_count - state.eth1_deposit_index)

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)  # [Modified in EIP7251]
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    for_ops(body.execution_payload.withdraw_requests, process_execution_layer_withdraw_request)  # New in EIP7251
    for_ops(body.consolidations, process_consolidation)  # New in EIP7251
```

##### Deposits

###### Updated  `apply_deposit`

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
            PendingBalanceDeposit(index=index, amount=amount))  # [Modified in EIP-7251]
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
                               signature: BLSSignature) -> None:
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

```python
def add_validator_to_registry(state: BeaconState,
                              pubkey: BLSPubkey,
                              withdrawal_credentials: Bytes32,
                              amount: uint64) -> None:
    index = get_index_for_new_validator(state)
    validator = get_validator_from_deposit(pubkey, withdrawal_credentials)
    set_or_append_list(state.validators, index, validator)
    set_or_append_list(state.balances, index, 0)  # [Modified in EIP7251]
    set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.inactivity_scores, index, uint64(0))
    state.pending_balance_deposits.append(PendingBalanceDeposit(index=index, amount=amount))  # [New in EIP7251]
```

###### Updated `get_validator_from_deposit`

```python
def get_validator_from_deposit(pubkey: BLSPubkey, withdrawal_credentials: Bytes32) -> Validator:
    return Validator(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
        effective_balance=0,  # [Modified in EIP7251]
    )
```

##### Withdrawals 

###### New `process_execution_layer_withdraw_request`

```python
def process_execution_layer_withdraw_request(
    state: BeaconState,
    execution_layer_withdraw_request: ExecutionLayerWithdrawRequest
) -> None:
    amount = execution_layer_withdraw_request.amount
    is_full_exit_request = amount == 0
    # If partial withdrawal queue is full, only full exits are processed 
    if len(state.pending_partial_withdrawals) >= PENDING_PARTIAL_WITHDRAWALS_LIMIT and not is_full_exit_request:
        return

    validator_pubkeys = [v.pubkey for v in state.validators]
    index = ValidatorIndex(validator_pubkeys.index(execution_layer_withdraw_request.validator_pubkey))
    validator = state.validators[index]

    # Same conditions as in EIP-7002
    if not (
        has_execution_withdrawal_credential(validator)
        # Verify withdrawal credentials
        and validator.withdrawal_credentials[12:] == execution_layer_withdraw_request.source_address
        # Verify the validator is active
        and is_active_validator(validator, get_current_epoch(state))
        # Verify exit has not been initiated, and slashed
        and validator.exit_epoch == FAR_FUTURE_EPOCH
        # Verify the validator has been active long enough
        and get_current_epoch(state) >= validator.activation_epoch + SHARD_COMMITTEE_PERIOD
    ):
        return
    # New condition: only allow partial withdrawals with compounding withdrawal credentials
    if not (is_full_exit_request or has_compounding_withdrawal_credential(validator)):
        return

    pending_balance_to_withdraw = sum(
        item.amount for item in state.pending_partial_withdrawals if item.index == index
    )
    # only exit validator if it has no pending withdrawals in the queue
    if is_full_exit_request and pending_balance_to_withdraw > 0:
        return

    if is_full_exit_request:
        initiate_validator_exit(state, index)
    elif state.balances[index] > MIN_ACTIVATION_BALANCE + pending_balance_to_withdraw:
        to_withdraw = min(
            state.balances[index] - MIN_ACTIVATION_BALANCE - pending_balance_to_withdraw,
            amount
        )
        exit_queue_epoch = compute_exit_epoch_and_update_churn(state, to_withdraw)
        withdrawable_epoch = Epoch(exit_queue_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY)
        state.pending_partial_withdrawals.append(PartialWithdrawal(
            index=index,
            amount=to_withdraw,
            withdrawable_epoch=withdrawable_epoch,
        ))
```

##### Consolidations

###### New `process_consolidation`

```python
def process_consolidation(state: BeaconState, signed_consolidation: SignedConsolidation) -> None:
    # If the pending consolidations queue is full, no consolidations are allowed in the block
    assert len(state.pending_consolidations) < PENDING_CONSOLIDATIONS_LIMIT
    # If there is too little available consolidation churn limit, no consolidations are allowed in the block
    assert get_consolidation_churn_limit(state) > MIN_ACTIVATION_BALANCE
    consolidation = signed_consolidation.message
    # Verify that source != target, so a consolidation cannot be used as an exit.
    assert consolidation.source_index != consolidation.target_index

    source_validator = state.validators[consolidation.source_index]
    target_validator = state.validators[consolidation.target_index]
    # Verify the source and the target are active
    current_epoch = get_current_epoch(state)
    assert is_active_validator(source_validator, current_epoch)
    assert is_active_validator(target_validator, current_epoch)
    # Verify exits for source and target have not been initiated
    assert source_validator.exit_epoch == FAR_FUTURE_EPOCH
    assert target_validator.exit_epoch == FAR_FUTURE_EPOCH
    # Consolidations must specify an epoch when they become valid; they are not valid before then
    assert current_epoch >= consolidation.epoch 

    # Verify the source and the target have Execution layer withdrawal credentials
    assert has_execution_withdrawal_credential(source_validator)
    assert has_execution_withdrawal_credential(target_validator)
    # Verify the same withdrawal address
    assert source_validator.withdrawal_credentials[1:] == target_validator.withdrawal_credentials[1:]

    # Verify consolidation is signed by the source and the target
    domain = compute_domain(DOMAIN_CONSOLIDATION, genesis_validators_root=state.genesis_validators_root)
    signing_root = compute_signing_root(consolidation, domain)
    pubkeys = [source_validator.pubkey, target_validator.pubkey]
    assert bls.FastAggregateVerify(pubkeys, signing_root, signed_consolidation.signature)

    # Initiate source validator exit and append pending consolidation
    active_balance = get_active_balance(state, consolidation.source_index)
    source_validator.exit_epoch = compute_consolidation_epoch_and_update_churn(state, active_balance)
    source_validator.withdrawable_epoch = Epoch(
        source_validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    state.pending_consolidations.append(PendingConsolidation(
        source_index=consolidation.source_index,
        target_index=consolidation.target_index
    ))
```

