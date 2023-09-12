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
    - [New `get_validator_inbound_churn_limit`](#new-get_validator_inbound_churn_limit)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Registry updates](#registry-updates)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to limit the max inbound churn value, motivated to limit the validator active set growth rate.

*Note:* This specification is built upon [Capella](../../capella/beacon_chain.md) and is under active development.

## Configuration

### Validator cycle

| Name | Value |
| - | - |
| `MAX_PER_EPOCH_INBOUND_CHURN_LIMIT` | `uint64(12)` (= 12) |

## Helper functions

### Beacon state accessors

#### New `get_validator_inbound_churn_limit`

```python
def get_validator_inbound_churn_limit(state: BeaconState) -> uint64:
    """
    Return the validator inbound churn limit for the current epoch.
    """
    active_validator_indices = get_active_validator_indices(state, get_current_epoch(state))
    return min(
        MAX_PER_EPOCH_INBOUND_CHURN_LIMIT,
        max(
            MIN_PER_EPOCH_CHURN_LIMIT,
            uint64(len(active_validator_indices)) // CHURN_LIMIT_QUOTIENT,
        ),
    )
```

## Beacon chain state transition function

### Epoch processing

#### Registry updates

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

    # Queue validators eligible for activation and not yet dequeued for activation
    activation_queue = sorted([
        index for index, validator in enumerate(state.validators)
        if is_eligible_for_activation(state, validator)
        # Order by the sequence of activation_eligibility_epoch setting and then index
    ], key=lambda index: (state.validators[index].activation_eligibility_epoch, index))
    # Dequeued validators for activation up to churn limit
    # [Modified in limit churn]
    for index in activation_queue[:get_validator_inbound_churn_limit(state)]:
        validator = state.validators[index]
        validator.activation_epoch = compute_activation_exit_epoch(get_current_epoch(state))
```

