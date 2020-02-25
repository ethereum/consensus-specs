# Ethereum 2.0 Phase 2 -- The Beacon Chain for Sharded Execution Environments

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Configuration](#configuration)
  - [Misc](#misc)
- [New containers](#new-containers)
  - [`ExecutionEnvironmentData`](#executionenvironmentdata)
  - [New `EETransaction`](#new-eetransaction)
  - [New `EECall`](#new-eecall)
  - [New `ShardStateContents`](#new-shardstatecontents)
  - [New `ShardBlockContents`](#new-shardblockcontents)
- [Updated containers](#updated-containers)
  - [Extended `ShardState`](#extended-shardstate)
  - [Extended `BeaconState`](#extended-beaconstate)
  - [Extended `BeaconBlockBody`](#extended-beaconblockbody)
  - [Extended `BeaconBlock`](#extended-beaconblock)
    - [Extended `SignedBeaconBlock`](#extended-signedbeaconblock)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes the extensions made to the Phase 1 design of The Beacon Chain
 to facilitate the execution capabilities as part of Phase 2 of Eth2.

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `EEIndex` | `uint64` | an Execution Environment index |

## Configuration

Configuration is not namespaced. Instead it is strictly an extension;
 no constants of phase 0 change, but new constants are adopted for changing behaviors.

### Misc

| Name | Value | Unit | Description | 
| - | - | - |
| `MAX_EXECUTION_ENVIRONMENT_CODE_SIZE` | `2**24` (= 16 MiB) | TBD: how large can an EE be? |
| `MAX_EE_WITNESS_SIZE` | `2**18` (= 1/4 MiB) | TBD: how large can an EE witness be? Avoid one EE taking all space to incentivize more EEs? |
| `MAX_EXECUTION_ENVIRONMENTS` | `2**10` | TBD: capacity for how many EEs? |
| `MAX_TRANSACTION_CALL_SIZE` | `2**12` (= 4 KiB) | TBD: how big can a transaction call be? |
| `MAX_TRANSACTION_WITNESS_SIZE` | `2**12` (= 4 KiB) | TBD: how big can a transaction witness be? |
| `MAX_EE_CALL_SIZE` | `2**18` (= 1/4 MiB) | TBD: when transaction calls merge/enumerate, what is a suitable maximum resulting CALL data to pass to an EE? |
| `MAX_SHARD_BLOCK_CALLS` | `2**10` (= 1024) | TBD: calls per block per shard |
| `MAX_BEACON_MULTIPROOF_SIZE` | 2**12 (= 4 KiB) | TBD: maximum proof size of BeaconState |

## New containers

The following containers are new in Phase 1.

### `ExecutionEnvironmentData`

```python
class ExecutionEnvironmentData(Container):
    code: ByteList[MAX_EXECUTION_ENVIRONMENT_CODE_SIZE]
```

### New `EETransaction`

```python
class EETransaction(Container):
    # Where the transaction should execute
    shard: Shard
    ee_index: EEIndex
    # Passed as CALL input to the EE (contains account-abstracted signature and fee payment)
    call_data: ByteList[MAX_TRANSACTION_CALL_SIZE]
    # Passed as WITNESS input to the EE, aggregated with other transactions before execution
    witnesses: List[EEWitness, MAX_EXECUTION_ENVIRONMENTS]
```

### New `EEWitness`

```python
class EEWitness(Container):
    ee_index: EEIndex
    witness: ByteList[MAX_EE_WITNESS_SIZE]
```

### New `EECall`

```python
class EECall(Container):
    ee_index: EEIndex
    call_data: ByteList[MAX_TRANSACTION_CALL_SIZE]
```

### New `ShardStateContents`

The `ShardState.shard_state_contents_root` gets an enshrined expansion to `shard_state_contents` in Phase 2:

```python
class ShardStateContents(Container):
    ee_roots: List[Root, MAX_EXECUTION_ENVIRONMENTS]  # Roots of 'EEHeader' entries for respective EE.
```

### New `EEHeader`

```python
class EEHeader(Container):
    state_root: Root    # Root produced by the ExecutionEnvironment runtime.
    ee_funds: Gwei
```

### New `NettingRow`

```python
class NettingRow(Container):
    outgoing_shard_funds: List[Gwei, MAX_SHARDS]
```

#### New `NettingProof`

```python
class NettingProof(Container):
    # The values packed in the root are packed along the row, sourced from a single shard.
    # Note: the value of interest is in (let i = (shard % (32 // 8))): root[i * 8:(i+1) * 8]
    leaf_root: Root
    proof: Vector[Root, MAX_SHARDS_DEPTH]
```

#### New `NettingColumn`

```python
class NettingColumn(Container):
    incoming_shard_funds: List[NettingProof, MAX_SHARDS]
```

### New `ShardBlockContents`

The `ShardBlock.body` gets an enshrined meaning in Phase 2. It is serialized/deserialized to `ByteList[MAX_SHARD_BLOCK_SIZE]` using SSZ.

TODO: mixing in serialization is not pretty, try to enable merkle-proofs through block-data bytes.

```python
class ShardBlockContents(Container):
    beacon_multiproof: ByteList[MAX_BEACON_MULTIPROOF_SIZE]  # contains shard_states with shard roots expanded into 
    ee_headers: SparseList[EEHeader, MAX_EXECUTION_ENVIRONMENTS]
    ee_witnesses: SparseList[ByteList[MAX_EE_WITNESS_SIZE], MAX_EXECUTION_ENVIRONMENTS]
    ee_calls: List[EECall, MAX_SHARD_BLOCK_CALLS]
    shard_incoming_funds: SparseList[NettingColumn, MAX_SHARDS]
```

## Updated containers

The following containers have updated definitions in Phase 2.

### Extended `BeaconState`

TODO: We can register EEs in the BeaconState.

## Partials

To make state partially available to shards, a multi-proof is provided in the shard block data, covering just those parts of the state the shard-transition needs.

### `BeaconInformation`

```python
BeaconInformation = partial(BeaconState, [
    'slot'
    'shard_states' / ... # TODO with expansion into Shard state data (e.g. EE roots)
])
```

### `ShardStatePartial`
