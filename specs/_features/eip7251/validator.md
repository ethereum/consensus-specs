# Phase 0 -- Honest Validator

This is an accompanying document to [Phase 0 -- The Beacon Chain](./beacon-chain.md), which describes the expected actions of a "validator" participating in the Ethereum proof-of-stake protocol.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Attestation aggregation](#attestation-aggregation)
    - [Aggregation selection](#aggregation-selection)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement Deneb.

## Beacon chain responsibilities

### Attestation aggregation

#### Aggregation selection

Aggregator selection is now balance based. `state` is the `BeaconState` at the previous epoch of `slot` to allow lookahead.

```python
def is_aggregator(state: BeaconState, slot: Slot, index: CommitteeIndex, slot_signature: BLSSignature) -> bool:
    committee = get_beacon_committee(state, slot, index)
    committee_balance = get_total_balance(state, set(committee))
    balance = state.balances[validator]
    modulo = max(1, committee_balance // balance // TARGET_AGGREGATORS_PER_COMMITTEE)
    return bytes_to_uint64(hash(slot_signature)[0:8]) % modulo == 0
```

