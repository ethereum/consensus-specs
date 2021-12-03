# Crux -- The Beacon Chain

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Domain types](#domain-types)
- [Preset](#preset)
  - [Max operations per block](#max-operations-per-block)
  - [Time parameters](#time-parameters)
- [Configuration](#configuration)
  - [Gwei values](#gwei-values)
- [Containers](#containers)
  - [Extended containers](#extended-containers)
    - [`Validator`](#validator)
    - [`BeaconBlockBody`](#beaconblockbody)
  - [New containers](#new-containers)
    - [`DelegationMessage`](#delegationmessage)
    - [`Delegation`](#delegation)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Operations](#operations)
    - [Delegation](#delegation)
      - [`get_validator_from_delegation`](#get_validator_from_delegation)
      - [`process_delegation`](#process_delegation)
  - [Epoch processing](#epoch-processing)
    - [`process_delegation_transfers`](#process_delegation_transfers)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This upgrade adds validator delegation. A validator may choose to delegate all its earnings above `MAX_EFFECTIVE_BALANCE` to an existing or a new validator.

## Constants

### Domain types

| Name  | Value |
| - | - |
| `DOMAIN_DELEGATION` | `DomainType('0x0A000000')` |

## Preset

### Max operations per block

| Name | Value |
| - | - |
| `MAX_DELEGATIONS` | `2**4` (=16) |

### Time parameters
| Name | Value | Unit | Duration | 
| - | - | :-: | :-: |
| `MAX_DELEGATION_INCLUSION_DELAY` | `uint64(2**7)` (=128) | slots | 25.6 minutes | 

## Configuration

### Gwei values

| Name | Value |
| - | - |
| `DELEGATION_TRANSACTION_COST` | `Gwei(10**6)` (= 1,000,000) TBD |


## Containers

### Extended containers

#### `Validator`
The `Validator` container gains a new field `delegate` containing the validator index of the delegate validator. This field is initialized at the fork with the same validator index of the current validator. (N.B. implementers may chose to keep a separate map instead)

```python
class Validator(Container):
    pubkey: BLSPubkey
    delegate: ValidatorIndex  # [New in Crux]
    withdrawal_credentials: Bytes32
    effective_balance: Gwei
    slashed: boolean
    # Status epochs
    activation_eligibility_epoch: Epoch
    activation_epoch: Epoch
    exit_epoch: Epoch
    withdrawable_epoch: Epoch
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    # Operations
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    delegations: List[Delegation, MAX_DELEGATIONS]  # [New in Crux]
    sync_aggregate: SyncAggregate
    # Execution
    execution_payload: ExecutionPayload
```

### New containers

#### `DelegationMessage`

```python
class DelegationMessage(Container):
    delegating_index: ValidatorIndex
    delegating_pubkey: BLSPubkey
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
```

#### `Delegation`

```python
class Delegation(Container):
    message: DelegationMessage
    epoch: Epoch
    signature: BLSSignature
```

## Beacon chain state transition function

### Block processing

#### Operations

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
    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.delegations, process_delegation)   # [New in Crux]
```

#### Delegation

##### `get_validator_from_delegation`

```python
def get_validator_from_delegation_message(message: DelegationMessage, amount: Gwei) -> Validator:
    effective_balance = min(amount - amount % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE)
    return Validator(
        pubkey=message.pubkey,
        withdrawal_credentials=message.withdrawal_credentials,
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
        effective_balance=effective_balance,
    )
```

##### `process_delegation`

```python
def process_delegation(state: BeaconState, delegation: Delegation) -> None:
    message = delegation.message
    current_epoch = get_current_epoch(state)
    assert  message.epoch <= current.epoch <= message.epoch + MAX_DELEGATION_INCLUSION_DELAY

    delegating_index = message.delegating_index
    min_delegating_balance = MAX_EFFECTIVE_BALANCE + MIN_DEPOSIT_AMOUNT + DELEGATION_TRANSACTION_COST
    assert state.balances[delegating_index] >= min_delegating_balance
    amount = state.balances[delegating_index] - MAX_EFFECTIVE_BALANCE - DELEGATION_TRANSACTION_COST

    delegating_validator = state.validators[delegating_index]
    assert is_active_validator(delegating_validator, current_epoch)
    assert delegating_validator.slashed == false

    assert delegating_validator.delegate == delegating_index

    delegating_pubkey = message.delegating_pubkey
    assert hash(delegating_pubkey)[1:] == delegating_validator.withdrawal_credentials[1:]

    domain = compute_domain(DOMAIN_DELEGATION)
    signing_root = compute_signing_root(message, domain)
    assert bls.Verify(delegating_pubkey, signing_root, delegation.signature)

    validator_pubkeys = [v.pubkey for v in state.validators]
    if pubkey not in validator_pubkeys:
        index = len(state.validators)
        state.validators.append(get_validator_from_delegation(message, amount))
    else:
        index = ValidatorIndex(validator_pubkeys.index(pubkey))
        assert index > delegating_index
        assert state.validators[index].exit_epoch == FAR_FUTURE_EPOCH

    delegating_validator.delegate = index
    proposer_index = get_beacon_proposer_index(state)
    decrease_balance(state, delegating_validator, amount + DELEGATION_TRANSACTION_COST)
    increase_balance(state, index, amount)
    increase_balance(state, proposer_index, DELEGATION_TRANSACTION_COST)
```

### Epoch processing

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_delegation_transfers(state)  # [New in Crux]
    process_registry_updates(state)   # [Modified in Crux]
    process_slashings(state)
    process_eth1_data_reset(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_roots_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
```

#### `process_delegation_transfers`

```python
def process_delegation_transfers(state: BeaconState) -> None:
    delegating_validators = [(i, v) for i, v in enumerate(state.validators) if v.delegate > i and not v.slashed]
    for index, validator in delegating_validators:
        if state.balance[index] > MAX_EFFECTIVE_BALANCE:
            delegate_validator = state.validators[validator.delegate]
            if delegate_validator.exit_epoch == FAR_FUTURE_EPOCH:
                amount = state_balance[index] - MAX_EFFECTIVE_BALANCE
                state_balance[index] = MAX_EFFECTIVE_BALANCE
                increase_balance(state, validator.delegate, amount)
```
