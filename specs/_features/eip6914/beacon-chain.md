# EIP-6914 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Preset](#preset)
  - [Time parameters](#time-parameters)
- [Helper functions](#helper-functions)
  - [Predicates](#predicates)
    - [`is_reusable_validator`](#is_reusable_validator)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Modified `get_index_for_new_validator`](#modified-get_index_for_new_validator)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to assign new deposits to existing validator records. Refers to [EIP-6914](https://github.com/ethereum/EIPs/pull/6914).

*Note*: This specification is built upon [Capella](../../capella/beacon-chain.md) and is under active development.

## Preset

### Time parameters

| Name | Value | Unit | Duration |
| - | - | - | - |
| `SAFE_EPOCHS_TO_REUSE_INDEX` | `uint64(2**16)` (= 65,536) | epochs | ~0.8 year |

## Helper functions

### Predicates

#### `is_reusable_validator`

```python
def is_reusable_validator(validator: Validator, balance: Gwei, epoch: Epoch) -> bool:
    """
    Check if ``validator`` index can be re-assigned to a new deposit.
    """
    return (
        epoch > validator.withdrawable_epoch + SAFE_EPOCHS_TO_REUSE_INDEX
        and balance == 0
    )
```

## Beacon chain state transition function

### Block processing

#### Modified `get_index_for_new_validator`

```python
def get_index_for_new_validator(state: BeaconState) -> ValidatorIndex:
    for index, validator in enumerate(state.validators):
        if is_reusable_validator(validator, state.balances[index], get_current_epoch(state)):
            return ValidatorIndex(index)
    return ValidatorIndex(len(state.validators))
```
