# Hysteresis-fix -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Epoch processing](#epoch-processing)
    - [Effective balances updates](#effective-balances-updates)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This upgrade change hysteresis to only apply to active validator

## Beacon chain state transition function

### Epoch processing

#### Effective balances updates

```python
def process_effective_balance_updates(state: BeaconState) -> None:
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        HYSTERESIS_INCREMENT = uint64(EFFECTIVE_BALANCE_INCREMENT // HYSTERESIS_QUOTIENT)
        DOWNWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_DOWNWARD_MULTIPLIER
        UPWARD_THRESHOLD = HYSTERESIS_INCREMENT * HYSTERESIS_UPWARD_MULTIPLIER
        # Update effective balances with hysteresis when active validator
        if is_active_validator(validator, get_current_epoch(state)):
            if (
                (balance + DOWNWARD_THRESHOLD < validator.effective_balance
                    or validator.effective_balance + UPWARD_THRESHOLD < balance)
            ):
                validator.effective_balance = min(
                    balance - balance % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE)
        # Update effective balances without hysteresis when inactive validator
        else:
            validator.effective_balance = min(balance, MAX_EFFECTIVE_BALANCE)
```
