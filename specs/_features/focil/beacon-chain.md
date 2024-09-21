# FOCIL -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Domain types](#domain-types)
- [Preset](#preset)
  - [Inclusion List Committee](#inclusion-list-committee)
  - [Execution](#execution)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`InclusionSummary`](#inclusionsummary)
    - [`LocalInclusionList`](#localinclusionlist)
    - [`SignedLocalInclusionList`](#signedlocalinclusionlist)
  - [Predicates](#predicates)
    - [New `is_valid_local_inclusion_list_signature`](#new-is_valid_local_inclusion_list_signature)
  - [Beacon State accessors](#beacon-state-accessors)
    - [`get_inclusion_list_committee`](#get_inclusion_list_committee)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to add a fork-choice enforced, committee-based inclusion list (FOCIL) mechanism to allow forced transaction inclusion. Refers to [Ethresearch](https://ethresear.ch/t/fork-choice-enforced-inclusion-lists-focil-a-simple-committee-based-inclusion-list-proposal/19870/1)

*Note:* This specification is built upon [Electra](../../electra/beacon_chain.md) and is under active development.

## Constants

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_IL_COMMITTEE`       | `DomainType('0x0C000000')`  # (New in FOCIL)|

## Preset

### Inclusion List Committee

| Name | Value | 
| - | - | 
| `IL_COMMITTEE_SIZE` | `uint64(2**9)` (=256)  # (New in FOCIL) |

### Execution

| Name | Value |
| - | - |
| `MAX_TRANSACTIONS_PER_INCLUSION_LIST` |  `uint64(1)` # (New in FOCIL) TODO: Placeholder | 

## Containers

### New containers

#### `InclusionSummary`

```python
class InclusionSummary(Container):
    address: ExecutionAddress
    nonce: uint64
    gas_limit: uint64
```

#### `LocalInclusionList`

```python
class LocalInclusionList(Container):
    slot: Slot
    validator_index: ValidatorIndex
    parent_root: Root
    parent_hash: Hash32
    summaries: List[InclusionSummary, MAX_TRANSACTIONS_PER_INCLUSION_LIST]
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST]
```

#### `SignedLocalInclusionList`

```python
class SignedLocalInclusionList(Container):
    message: LocalInclusionList
    signature: BLSSignature
```

### Predicates

#### New `is_valid_local_inclusion_list_signature`

```python
def is_valid_local_inclusion_list_signature(
        state: BeaconState, 
        signed_local_inclusion_list: SignedLocalInclusionList) -> bool:
    """
    Check if ``signed_local_inclusion_list`` has a valid signature
    """
    message = signed_local_inclusion_list.message
    index = message.validator_index
    pubkey = state.validators[index].pubkey
    domain = get_domain(state, IL_COMMITTEE_SIZE, compute_epoch_at_slot(message.slot))
    signing_root = compute_signing_root(message, domain)
    return bls.FastAggregateVerify(pubkey, signing_root, signed_local_inclusion_list.signature)
```

### Beacon State accessors

#### `get_inclusion_list_committee`

```python
def get_inclusion_list_committee(state: BeaconState, slot: Slot) -> Vector[ValidatorIndex, IL_COMMITTEE_SIZE]:
    """
    Get the inclusion list committee for the given ``slot``
    """
    epoch = compute_epoch_at_slot(slot)
    committees_per_slot = bit_floor(min(get_committee_count_per_slot(state, epoch), IL_COMMITTEE_SIZE))
    members_per_committee = IL_COMMITTEE_SIZE // committees_per_slot
    
    validator_indices: List[ValidatorIndex] = [] 
    for idx in range(committees_per_slot):
        beacon_committee = get_beacon_committee(state, slot, CommitteeIndex(idx))
        validator_indices += beacon_committee[:members_per_committee]
    return validator_indices
```
