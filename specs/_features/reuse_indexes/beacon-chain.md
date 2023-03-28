# Reuse indexes -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Preset](#preset)
  - [Time parameters](#time-parameters)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Modified `assign_index_to_deposit`](#modified-assign_index_to_deposit)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to assign new deposits to existing validator records that have withdrawn long ago.

*Note:* This specification is built upon [Capella](../../capella/beacon_chain.md) and is under active development.

## Preset

### Time parameters

| Name | Value | Unit | Duration |
| - | - | - |
| `REUSE_VALIDATOR_INDEX_DELAY` | `uint64(2**16)` (= 65,536) | epochs | ~1 year |

## Beacon chain state transition function

### Block processing

#### Modified `assign_index_to_deposit`

```python
def assign_index_to_deposit(state: BeaconState) -> int:
    for index, validator in enumerate(state.validators):
        if validator.withdrawable_epoch < get_current_epoch(state) - REUSE_VALIDATOR_INDEX_DELAY:
            return index
    return len(state.validators)
```
