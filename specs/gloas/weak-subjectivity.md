# Gloas -- Weak Subjectivity Guide

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Weak Subjectivity Period](#weak-subjectivity-period)
  - [Calculating the Weak Subjectivity Period](#calculating-the-weak-subjectivity-period)
    - [Modified `compute_weak_subjectivity_period`](#modified-compute_weak_subjectivity_period)

<!-- mdformat-toc end -->

## Introduction

This document is an extension of the
[Electra -- Weak Subjectivity Guide](../electra/weak-subjectivity.md). All
behaviors and definitions defined in this document, and documents it extends,
carry over unless explicitly noted or overridden.

This document is a guide for implementing Weak Subjectivity protections in
Gloas. The Weak Subjectivity Period (WSP) calculations have changed in Gloas due
to EIP-8061, which separates activation, exit, and consolidation churn into
independently tunable parameters.

## Weak Subjectivity Period

### Calculating the Weak Subjectivity Period

#### Modified `compute_weak_subjectivity_period`

```python
def compute_weak_subjectivity_period(state: BeaconState) -> uint64:
    """
    Returns the weak subjectivity period for the current ``state``.
    This computation takes into account the effect of:
        - exit churn (weighted 2/3)
        - activation churn (weighted 1/3)
        - consolidation churn (weighted 1)
    """
    t = get_total_active_balance(state)
    delta = (
        2 * get_exit_churn_limit(state) // 3
        + get_activation_churn_limit(state) // 3
        + get_consolidation_churn_limit(state)
    )
    epochs_for_validator_set_churn = SAFETY_DECAY * t // (2 * delta * 100)
    return MIN_VALIDATOR_WITHDRAWABILITY_DELAY + epochs_for_validator_set_churn
```
