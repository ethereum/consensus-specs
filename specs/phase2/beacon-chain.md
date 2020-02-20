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
    witness: ByteList[MAX_TRANSACTION_WITNESS_SIZE]
```

### New `EECall`

```python
class EECall(Container):
    ee_index: EEIndex
    call_data: ByteList[MAX_TRANSACTION_CALL_SIZE]
```

### New `ShardStateContents`

The `ShardState.shard_state_contents_root` gets an enshrined meaning in Phase 2:

```python
class ShardStateContents(Container):
    ee_roots: List[Root, MAX_EXECUTION_ENVIRONMENTS]
```

### New `ShardBlockContents`

The `ShardBlock.body` gets an enshrined meaning in Phase 2. It is serialized/deserialized to `ByteList[MAX_SHARD_BLOCK_SIZE]` using SSZ.

TODO: mixing in serialization is not pretty, try to enable merkle-proofs through block-data bytes.

```python
class ShardBlockContents(Container):
    ee_calls: List[EECall, MAX_SHARD_BLOCK_CALLS]
    ee_witnesses: SparseList[ByteList[MAX_EE_WITNESS_SIZE], MAX_EXECUTION_ENVIRONMENTS]
```

## Updated containers

The following containers have updated definitions in Phase 2.

### Extended `ShardState`

Note that instead of just a root, contents are expanded, but constrained by EE count. 
```python
class ShardState(Container):
    slot: Slot
    gasprice: Gwei
    shard_state_contents: ShardStateContents
    shard_parent_root: Root
```

### Extended `BeaconState`

Note that `ShardState` in the Phase1 `shard_states` has a new definition.

```python
class BeaconState(Container):
    # Versioning
    genesis_time: uint64
    slot: Slot
    fork: Fork
    # History
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]
    # Eth1
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, SLOTS_PER_ETH1_VOTING_PERIOD]
    eth1_deposit_index: uint64
    # Registry
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    # Randomness
    randao_mixes: Vector[Root, EPOCHS_PER_HISTORICAL_VECTOR]
    # Slashings
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]  # Per-epoch sums of slashed effective balances
    # Attestations
    previous_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    current_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint  # Previous epoch snapshot
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    # Phase 1
    shard_states: List[ShardState, MAX_SHARDS]
    online_countdown: List[OnlineEpochs, VALIDATOR_REGISTRY_LIMIT]  # not a raw byte array, considered its large size.
    current_light_committee: CompactCommittee
    next_light_committee: CompactCommittee
    # Custody game
    # Future derived secrets already exposed; contains the indices of the exposed validator
    # at RANDAO reveal period % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS
    exposed_derived_secrets: Vector[List[ValidatorIndex, MAX_EARLY_DERIVED_SECRET_REVEALS * SLOTS_PER_EPOCH],
                                    EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS]
    # Phase 2
    execution_environments: List[ExecutionEnvironmentData, MAX_EXECUTION_ENVIRONMENTS]
```

### Extended `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data  # Eth1 data vote
    graffiti: Bytes32  # Arbitrary data
    # Slashings
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    # Attesting
    attestations: List[Attestation, MAX_ATTESTATIONS]
    # Entry & exit
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    # Custody game
    custody_slashings: List[SignedCustodySlashing, MAX_CUSTODY_SLASHINGS]
    custody_key_reveals: List[CustodyKeyReveal, MAX_CUSTODY_KEY_REVEALS]
    early_derived_secret_reveals: List[EarlyDerivedSecretReveal, MAX_EARLY_DERIVED_SECRET_REVEALS]
    # Shards
    shard_transitions: Vector[ShardTransition, MAX_SHARDS]
    # Light clients
    light_client_signature_bitfield: Bitvector[LIGHT_CLIENT_COMMITTEE_SIZE]
    light_client_signature: BLSSignature
    # TODO: execution environment deployment? Or fork it in?
```

### Extended `BeaconBlock`

Note that the `body` has a new `BeaconBlockBody` definition.

```python
class BeaconBlock(Container):
    slot: Slot
    parent_root: Root
    state_root: Root
    body: BeaconBlockBody
```

#### Extended `SignedBeaconBlock`

Note that the `message` has a new `BeaconBlock` definition.

```python
class SignedBeaconBlock(Container):
    message: BeaconBlock
    signature: BLSSignature
```
