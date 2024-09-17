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
    - [`InclusionSummaryAggregate`](#inclusionsummaryaggregate)
    - [`IndexedInclusionSummaryAggregate`](#indexedinclusionsummaryaggregate)
    - [`InclusionSummaryAggregates`](#inclusionsummaryaggregates)
  - [Modified containers](#modified-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
  - [Beacon State accessors](#beacon-state-accessors)
    - [`get_inclusion_list_committee`](#get_inclusion_list_committee)
  - [Beacon State accessors](#beacon-state-accessors-1)
    - [New `get_inclusion_summary_aggregates_signature_indices`](#new-get_inclusion_summary_aggregates_signature_indices)
    - [New `get_indexed_inclusion_summary_aggregate`](#new-get_indexed_inclusion_summary_aggregate)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution engine](#execution-engine)
    - [Engine APIs](#engine-apis)
      - [New `verify_and_notify_local_inclusion_list`](#new-verify_and_notify_local_inclusion_list)
  - [Block processing](#block-processing)
    - [Operations](#operations)
      - [Modified `process_operations`](#modified-process_operations)
      - [Inclusion list aggregate](#inclusion-list-aggregate)
        - [New `process_inclusion_list_aggregate`](#new-process_inclusion_list_aggregate)

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

#### `InclusionSummaryAggregate`

```python
class InclusionSummaryAggregate(Container):
    aggregation_bits: Bitvector[IL_COMMITTEE_SIZE]
    summary: InclusionSummary
    signature: BLSSignature
```

#### `IndexedInclusionSummaryAggregate`

```python
class IndexedInclusionSummaryAggregate(Container):
    validator_indices: List[ValidatorIndex, IL_COMMITTEE_SIZE]
    summary: InclusionSummary
    signature: BLSSignature
```

#### `InclusionSummaryAggregates`

```python
class InclusionSummaryAggregates(Container):
    List[InclusionSummaryAggregate, MAX_TRANSACTIONS_PER_INCLUSION_LIST * IL_COMMITTEE_SIZE]
```

### Modified containers

#### `BeaconBlockBody`

**Note:** The Beacon Block body is modified to contain a new `inclusion_summary_aggregates` field.

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
    inclusion_summary_aggregates: InclusionSummaryAggregates   # [New in FOCIL]
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
### Beacon State accessors

#### New `get_inclusion_summary_aggregates_signature_indices`

```python
def get_inclusion_summary_aggregates_signature_indices(state: BeaconState, 
                                  inclusion_summary_aggregate: InclusionSummaryAggregate) -> Set[ValidatorIndex]:
    """
    Return the set of indices corresponding to ``inclusion_summary_aggregate``.
    """
    il_committee = get_inclusion_list_committee(state, state.slot)
    return set(index for i, index in enumerate(il_committee) if inclusion_summary_aggregate.aggregation_bits[i])
```

#### New `get_indexed_inclusion_summary_aggregate`

```python
def get_indexed_inclusion_summary_aggregate(state: BeaconState, 
                                    inclusion_summary_aggregate: InclusionSummaryAggregate) -> IndexedInclusionSummaryAggregate:
    """
    Return the indexed inclusion list aggregate corresponding to ``inclusion_summary_aggregate``.
    """
    indices = get_inclusion_summary_aggregates_signature_indices(state, inclusion_summary_aggregate)

    return IndexedInclusionSummaryAggregate(
        validator_indices=sorted(indices),
        summary=inclusion_summary_aggregate.summary,
        signature=inclusion_summary_aggregate.signature,
    )
```

## Beacon chain state transition function

### Execution engine

#### Engine APIs

##### New `verify_and_notify_local_inclusion_list`

```python
def verify_and_notify_local_inclusion_list(self: ExecutionEngine,
                              inclusion_list: LocalInclusionList) -> bool:
    """
    Return ``True`` if and only if the transactions in the inclusion list can be successfully executed
    starting from the execution state corresponding to the `parent_hash` in the inclusion list 
    summary.
    """
    ...
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_withdrawals(state, block.body.execution_payload)
    process_execution_payload(state, block.body, EXECUTION_ENGINE)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)  # [Modified in FOCIL]
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### Operations

##### Modified `process_operations`

*Note*: The function `process_operations` is modified to support all of the new functionality in FOCIL.

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    eth1_deposit_index_limit = min(state.eth1_data.deposit_count, state.deposit_requests_start_index)
    if state.eth1_deposit_index < eth1_deposit_index_limit:
        assert len(body.deposits) == min(MAX_DEPOSITS, eth1_deposit_index_limit - state.eth1_deposit_index)
    else:
        assert len(body.deposits) == 0

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)
    for_ops(body.execution_payload.deposit_requests, process_deposit_request)
    for_ops(body.execution_payload.withdrawal_requests, process_withdrawal_request)
    for_ops(body.execution_payload.consolidation_requests, process_consolidation_request)
    for_ops(body.inclusion_summary_aggregate, process_inclusion_list_aggregate)   # [New in FOCIL]
```

##### Inclusion list aggregate

###### New `process_inclusion_list_aggregate`

```python
def process_inclusion_list_aggregate(
    state: BeaconState,
    inclusion_summary_aggregate: InclusionSummaryAggregate
) -> None:

    # Verify inclusion list aggregate signature
    indexed_inclusion_list_aggregate = get_indexed_inclusion_summary_aggregate(state, inclusion_summary_aggregate)
    assert is_valid_indexed_inclusion_list_aggregate(state, indexed_inclusion_list_aggregate)

    # TODO: Reward inclusion list aggregate participants
```