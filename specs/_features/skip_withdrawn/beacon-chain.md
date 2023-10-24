# Skip withdrawn validators -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Preset](#preset)
  - [Time parameters](#time-parameters)
- [Helper functions](#helper-functions)
  - [Predicates](#predicates)
    - [`is_skippable_validator`](#is_skippable_validator)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Modified `get_expected_withdrawals`](#modified-get_expected_withdrawals)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to skip validators that have withdrawn long ago in the withdrawal sweep.

This improvement is an alternative to [EIP-6914](https://github.com/ethereum/EIPs/pull/6914), which tries to reuse the validator indices that have withdrawn long ago. If we don't want to apply that EIP, we can apply this one instead to get the withdrawal process faster.

*Note:* This specification is built upon [Capella](../../capella/beacon_chain.md) and is under active development.

## Preset

### Time parameters

| Name | Value | Unit | Duration |
| - | - | - | - |
| `SAFE_EPOCHS_TO_SKIP` | `uint64(2**16)` (= 65,536) | epochs | ~0.8 year |

## Helper functions

### Predicates

#### `is_skippable_validator`

```python
def is_skippable_validator(validator: Validator, balance: Gwei, epoch: Epoch) -> bool:
    """
    Check if ``validator`` index can be skipped in the withdrawal sweep.
    """
    return (
        epoch > validator.withdrawable_epoch + SAFE_EPOCHS_TO_SKIP
        and balance == 0
    )
```

## Beacon chain state transition function

### Block processing

#### Modified `get_expected_withdrawals`

*Note*: The function `get_expected_withdrawals` is modified in a way that it will not
always run in the order of `MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP` anymore, but clients
SHOULD implement this function in a way that keeps the running time to be still in the
order of `MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP` by having a cache of unskippable
validators.

```python
def get_expected_withdrawals(state: BeaconState) -> Sequence[Withdrawal]:
    epoch = get_current_epoch(state)
    withdrawal_index = state.next_withdrawal_index
    validator_index = state.next_withdrawal_validator_index
    withdrawals: List[Withdrawal] = []
    bound = min(len(state.validators), MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
    for _ in range(bound):
        validator = state.validators[validator_index]
        balance = state.balances[validator_index]

        while is_skippable_validator(validator, balance):
            validator_index = ValidatorIndex((validator_index + 1) % len(state.validators))
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
                amount=balance - MAX_EFFECTIVE_BALANCE,
            ))
            withdrawal_index += WithdrawalIndex(1)
        if len(withdrawals) == MAX_WITHDRAWALS_PER_PAYLOAD:
            break
        validator_index = ValidatorIndex((validator_index + 1) % len(state.validators))
    return withdrawals
```
