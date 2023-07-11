Limit churn -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Validator cycle](#validator-cycle)
- [Helper functions](#helper-functions)
  - [Beacon state accessors](#beacon-state-accessors)
    - [modified `get_validator_churn_limit`](#modified-get_validator_churn_limit)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to limit the max churn value, motivated to limit the validator active set growth rate.

*Note:* This specification is built upon [Capella](../../capella/beacon_chain.md) and is under active development.

## Configuration

### Validator cycle

| Name | Value |
| - | - |
| `MAX_PER_EPOCH_CHURN_LIMIT` | `uint64(12)` (= 12) |

## Helper functions

### Beacon state accessors

#### modified `get_validator_churn_limit`

```python
def get_validator_churn_limit(state: BeaconState) -> uint64:
    """
    Return the validator churn limit for the current epoch.
    """
    active_validator_indices = get_active_validator_indices(state, get_current_epoch(state))
    return min(
      MAX_PER_EPOCH_CHURN_LIMIT,
      max(
        MIN_PER_EPOCH_CHURN_LIMIT,
        uint64(len(active_validator_indices)) // CHURN_LIMIT_QUOTIENT
      )
    )
```
