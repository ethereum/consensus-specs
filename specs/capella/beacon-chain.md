# Capella -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
- [Preset](#preset)
  - [State list lengths](#state-list-lengths)
- [Configuration](#configuration)
- [Containers](#containers)
  - [Extended Containers](#extended-containers)
    - [`Validator`](#validator)
    - [`BeaconState`](#beaconstate)
  - [New containers](#new-containers)
    - [`WithdrawalReceipt`](#withdrawalreceipt)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [`compute_withdrawal_tree_root`](#compute_withdrawal_tree_root)
  - [Beacon state mutators](#beacon-state-mutators)
    - [`withdraw`](#withdraw)
  - [Predicates](#predicates)
    - [`is_withdrawable_validator`](#is_withdrawable_validator)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Withdrawals](#withdrawals)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

Capella is a consensus-layer upgrade containin a number of features related
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
| `WITHDRAWAL_RECEIPTS_TREE_DEPTH` | `uint64(40)` (= 1,099,511,627,776) | capacity for `2**40` withdrawal receipts |

## Configuration

## Containers

### Extended Containers

#### `Validator`

```python
class Validator(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32  # Commitment to pubkey for withdrawals
    effective_balance: Gwei  # Balance at stake
    slashed: boolean
    # Status epochs
    activation_eligibility_epoch: Epoch  # When criteria for activation were met
    activation_epoch: Epoch
    exit_epoch: Epoch
    withdrawable_epoch: Epoch  # When validator can withdraw funds
    withdrawn_epoch: Epoch  # [New in Capella]
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
    latest_execution_payload_header: ExecutionPayloadHeader
    # Withdrawals  [New in Capella]
    withdrawal_receipts_merkle_stack: Vector[Root, WITHDRAWAL_RECEIPTS_TREE_DEPTH]
    withdrawal_count: uint64
    latest_withdrawal_tree_root: Root
```

### New containers

#### `WithdrawalReceipt`

```python
class WithdrawalReceipt(Container):
    index: WithdrawalReceiptIndex
    address: ExecutionAddress
    amount: Gwei
```

## Helper functions

### Misc

#### `compute_withdrawal_tree_root`

```python
def compute_withdrawal_tree_root(state: BeaconState) -> Root:
    """
    Computes the withdrawal-tree hash-tree-root,
    emulating a List[WithdrawalReceipt, 2**WITHDRAWAL_RECEIPTS_TREE_DEPTH].
    """
    zero_hashes = [Root()]
    for i in range(WITHDRAWAL_RECEIPTS_TREE_DEPTH - 1):
        zero_hashes.append(hash(zero_hashes[i] + zero_hashes[i]))

    size = int(state.withdrawal_count)
    node = Root()
    for height in range(WITHDRAWAL_RECEIPTS_TREE_DEPTH):
        if size % 2 == 1:
            node = hash(state.withdrawal_receipts_merkle_stack[i] + node)
        else:
            node = hash(node + zero_hashes[i])
        size /= 2
    return hash(node + uint256(state.withdrawal_count).encode_bytes())  # length mix-in
```

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
    # Optional: store receipt for later execution as user

    # Update state for computation of the withdrawal root
    node = hash_tree_root(receipt)
    size = uint64(index) + 1
    for i in range(WITHDRAWAL_RECEIPTS_TREE_DEPTH):
        if size % 2 == 1:  # odd size -> even position -> buffer left hand
            state.withdrawal_receipts_merkle_stack[i] = node
            break
        
        # combine previous left-hand with right hand
        node = hash(state.withdrawal_receipts_merkle_stack[i] + node)
        size /= 2
```

### Predicates

#### `is_withdrawable_validator`

```python
def is_withdrawable_validator(validator: Validator, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is withdrawable.
    """
    is_eth1_withdrawal_prefix = validator.withdrawal_credentials[0:1] == ETH1_ADDRESS_WITHDRAWAL_PREFIX
    return is_eth1_withdrawal_prefix and validator.withdrawable_epoch <= epoch < validator.withdrawn_epoch
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
    process_withdrawals(state)  # [New in Capella]
```

#### Withdrawals

*Note*: The function `process_withdrawals` is new.

```python
def process_withdrawals(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    for index, validator in enumerate(state.validators):
        if is_withdrawable_validator(validator, current_epoch):
            # TODO, consider the zero-balance case
            withdraw(state, ValidatorIndex(index), state.balances[index])
            validator.withdrawn_epoch = current_epoch
    state.latest_withdrawal_tree_root = compute_withdrawal_tree_root(state)
```
