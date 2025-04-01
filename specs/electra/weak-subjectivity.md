# Electra -- Weak Subjectivity Guide

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Weak Subjectivity Period](#weak-subjectivity-period)
  - [Calculating the Weak Subjectivity Period](#calculating-the-weak-subjectivity-period)
    - [Modified `compute_weak_subjectivity_period`](#modified-compute_weak_subjectivity_period)
    - [Modified `is_within_weak_subjectivity_period`](#modified-is_within_weak_subjectivity_period)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document is an extension of the [Phase 0 -- Weak Subjectivity
Guide](../phase0/weak-subjectivity.md). All behaviors and definitions defined in this document, and
documents it extends, carry over unless explicitly noted or overridden.

This document is a guide for implementing Weak Subjectivity protections in Electra. The Weak
Subjectivity Period (WSP) calculations have changed in Electra due to EIP-7251, which increases the
maximum effective balance for validators and allows validators to consolidate.

## Weak Subjectivity Period

### Calculating the Weak Subjectivity Period

#### Modified `compute_weak_subjectivity_period`

```python
def compute_weak_subjectivity_period(state: BeaconState) -> uint64:
    """
    Returns the weak subjectivity period for the current ``state``.
    This computation takes into account the effect of:
        - validator set churn (bounded by ``get_balance_churn_limit()`` per epoch)
    A detailed calculation can be found at:
    https://notes.ethereum.org/@CarlBeek/electra_weak_subjectivity
    """
    t = get_total_active_balance(state)
    delta = get_balance_churn_limit(state)
    epochs_for_validator_set_churn = SAFETY_DECAY * t // (4 * delta * 100)
    return MIN_VALIDATOR_WITHDRAWABILITY_DELAY + epochs_for_validator_set_churn
```

#### Modified `is_within_weak_subjectivity_period`

```python
def is_within_weak_subjectivity_period(store: Store, ws_state: BeaconState, ws_checkpoint: Checkpoint) -> bool:
    # Clients may choose to validate the input state against the input Weak Subjectivity Checkpoint
    assert ws_state.latest_block_header.state_root == ws_checkpoint.root
    assert compute_epoch_at_slot(ws_state.slot) == ws_checkpoint.epoch

    ws_period = compute_weak_subjectivity_period(ws_state)  # [Modified in Electra]
    ws_state_epoch = compute_epoch_at_slot(ws_state.slot)
    current_epoch = compute_epoch_at_slot(get_current_slot(store))
    return current_epoch <= ws_state_epoch + ws_period
```
