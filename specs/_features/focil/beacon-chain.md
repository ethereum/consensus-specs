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
    - [`InclusionListSummary`](#inclusionlistsummary)
    - [`InclusionList`](#inclusionlist)
    - [`SignedInclusionList`](#signedinclusionlist)
    - [`InclusionListAggregate`](#inclusionlistaggregate)
    - [`IndexedInclusionListAggregate`](#indexedinclusionlistaggregate)
  - [Modified containers](#modified-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
  - [Beacon State accessors](#beacon-state-accessors)
    - [`get_inclusion_list_committee`](#get_inclusion_list_committee)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution engine](#execution-engine)
    - [Engine APIs](#engine-apis)
      - [New `verify_and_notify_new_inclusion_list`](#new-verify_and_notify_new_inclusion_list)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to add a committee-based inclusion list mechanism to allow forced transaction inclusion. Refers to [Ethresearch](https://ethresear.ch/t/fork-choice-enforced-inclusion-lists-focil-a-simple-committee-based-inclusion-list-proposal/19870/1)

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
| `IL_COMMITTEE_SIZE` | `uint64(2**9)` (=512)  # (New in FOCIL) |

### Execution

| Name | Value |
| - | - |
| `MAX_TRANSACTIONS_PER_INCLUSION_LIST` |  `uint64(1)` # (New in FOCIL) | #TODO: Fill this value

## Containers

### New containers

#### `InclusionListSummary`

```python
class InclusionListSummary(Container):
    address: ExecutionAddress
    nonce: uint64
    gas_limit: uint64
```

#### `InclusionList`

```python
class InclusionList(Container):
    slot: Slot
    validator_index: ValidatorIndex
    parent_hash: Hash32
    summaries: List[InclusionListSummary, MAX_TRANSACTIONS_PER_INCLUSION_LIST]
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST]
```

#### `SignedInclusionList`

```python
class SignedInclusionList(Container):
    message: InclusionList
    signature: BLSSignature
```

#### `InclusionListAggregate`

```python
class InclusionListAggregate(Container):
    aggregation_bits: Bitvector[IL_COMMITTEE_SIZE]
    summary: InclusionListSummary
    signature: BLSSignature
```

#### `IndexedInclusionListAggregate`

```python
class IndexedInclusionListAggregate(Container):
    validator_indices: List[ValidatorIndex, IL_COMMITTEE_SIZE]
    message: InclusionList
    signature: BLSSignature
```

### Modified containers

#### `BeaconBlockBody`

**Note:** The Beacon Block body is modified to contain a new `inclusion_list_aggregate` field.

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data  # Eth1 data vote
    graffiti: Bytes32  # Arbitrary data
    # Operations
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS_ELECTRA]
    attestations: List[Attestation, MAX_ATTESTATIONS_ELECTRA]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    # FOCIL
    inclusion_list_aggregate: List[InclusionListAggregate, MAX_TRANSACTIONS_PER_INCLUSION_LIST]   # [New in FOCIL]
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

## Beacon chain state transition function

### Execution engine

#### Engine APIs

##### New `verify_and_notify_new_inclusion_list`

```python
def verify_and_notify_new_inclusion_list(self: ExecutionEngine,
                              inclusion_list: InclusionList) -> bool:
    """
    Return ``True`` if and only if the transactions in the inclusion list can be successfully executed
    starting from the execution state corresponding to the `parent_hash` in the inclusion list 
    summary.
    """
    ...
```