# Cappela -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

Cappela is a consensus-layer upgrade containin a number of features related
to validator withdrawals. Including:
* Automatic withdrawals of `withdrawable` validators
* Partial withdrawals during block proposal
* Operation to change from `BLS_WITHDRAWAL_PREFIX` to
  `ETH1_ADDRESS_WITHDRAWAL_PREFIX` versioned withdrawal credentials to enable withdrawals for a validator

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `WithdrawalReceiptIndex` | `uint64` | a withdrawal receipt index |

## Constants

## Preset

### State list lengths

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `WITHDRAWAL_RECEIPT_LIMIT` | `uint64(2**40)` (= 1,099,511,627,776) | withdrawal receipts|

## Configuration

## Containers

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
    withdrawal_receipts: List[WithdrawalReceipt, WITHDRAWAL_RECEIPT_LIMIT]  # [New in Cappela]
```

### New containers

#### `WithdrawalReceipt`

```python
class WithdrawalReceipt(Container):
    index: WithdrawalReceiptIndex
    address: ExecutionAddress
    amount: Gwei
```

## Helpers

### Beacon state mutators

#### `withdraw`

```python
def withdraw(state: BeaconState, index: ValidatorIndex, amount: Gwei) -> None:
    # Decrease the validator's balance
    decrease_balance(state, index, amount)
    # Create a corresponding withdrawal receipt
    receipt = WithdrawalReceipt(
        index=WithdrawalReceiptIndex(len(state.withdrawal_receipts)),
        address=state.validators[index].withdrawal_credentials[12:],
        amount=amount,
    )
    state.withdrawal_receipts.append(receipt)
```

### Predicates

#### `is_withdrawable_validator`

```python
def is_withdrawable_validator(validator: Validator, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is withdrawable.
    """
    return validator.withdrawable_epoch <= epoch
```

## Beacon chain state transition function

### Epoch processing

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_roots_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
    process_withdrawals(state)  # [New in Cappela]
```

#### Withdrawals

*Note*: The function `process_withdrawals` is new.

```python
def process_withdrawals(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        is_balance_nonzero = state.balances[index] == 0
        is_eth1_withdrawal_prefix = validator.withdrawal_credentials[0] == ETH1_ADDRESS_WITHDRAWAL_PREFIX
        if is_balance_nonzero and is_eth1_withdrawal_prefix and is_withdrawable_validator(validator, current_epoch):
            withdraw(state, ValidatorIndex(index), balance)
```
