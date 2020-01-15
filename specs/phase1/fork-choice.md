# Ethereum 2.0 Phase 1 -- Beacon Chain Fork Choice

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
- [Fork choice](#fork-choice)
  - [Handlers](#handlers)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document is the beacon chain fork choice spec for part of Ethereum 2.0 Phase 1.

## Fork choice

Due to the changes in the structure of `IndexedAttestation` in Phase 1, `on_attestation` must be re-specified to handle this. The bulk of `on_attestation` has been moved out into a few helpers to reduce code duplication where possible.

The rest of the fork choice remains stable.

### Handlers

```python
def on_attestation(store: Store, attestation: Attestation) -> None:
    """
    Run ``on_attestation`` upon receiving a new ``attestation`` from either within a block or directly on the wire.

    An ``attestation`` that is asserted as invalid may be valid at a later time,
    consider scheduling it for later processing in such case.
    """
    validate_on_attestation(store, attestation)
    store_target_checkpoint_state(store, attestation.data.target)

    # Get state at the `target` to fully validate attestation
    target_state = store.checkpoint_states[attestation.data.target]
    indexed_attestation = get_indexed_attestation(target_state, attestation)
    assert is_valid_indexed_attestation(target_state, indexed_attestation)

    # Update latest messages for attesting indices
    attesting_indices = [
        index for i, index in enumerate(indexed_attestation.committee)
        if attestation.aggregation_bits[i]
    ]
    update_latest_messages(store, attesting_indices, attestation)
```