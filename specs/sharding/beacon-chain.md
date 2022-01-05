# Sharding -- The Beacon Chain

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
  - [Glossary](#glossary)
- [Custom types](#custom-types)
- [Constants](#constants)
  - [Misc](#misc)
  - [Domain types](#domain-types)
  - [Shard Work Status](#shard-work-status)
  - [Misc](#misc-1)
  - [Participation flag indices](#participation-flag-indices)
  - [Incentivization weights](#incentivization-weights)
- [Preset](#preset)
  - [Misc](#misc-2)
  - [Shard blob samples](#shard-blob-samples)
  - [Precomputed size verification points](#precomputed-size-verification-points)
  - [Gwei values](#gwei-values)
- [Configuration](#configuration)
- [Updated containers](#updated-containers)
  - [`AttestationData`](#attestationdata)
  - [`BeaconBlockBody`](#beaconblockbody)
  - [`BeaconState`](#beaconstate)
- [New containers](#new-containers)
  - [`Builder`](#builder)
  - [`DataCommitment`](#datacommitment)
  - [`AttestedDataCommitment`](#attesteddatacommitment)
  - [`ShardBlobBody`](#shardblobbody)
  - [`ShardBlobBodySummary`](#shardblobbodysummary)
  - [`ShardBlob`](#shardblob)
  - [`ShardBlobHeader`](#shardblobheader)
  - [`SignedShardBlob`](#signedshardblob)
  - [`SignedShardBlobHeader`](#signedshardblobheader)
  - [`PendingShardHeader`](#pendingshardheader)
  - [`ShardBlobReference`](#shardblobreference)
  - [`ShardProposerSlashing`](#shardproposerslashing)
  - [`ShardWork`](#shardwork)
- [Helper functions](#helper-functions)
  - [Misc](#misc-3)
    - [`next_power_of_two`](#next_power_of_two)
    - [`compute_previous_slot`](#compute_previous_slot)
    - [`compute_updated_sample_price`](#compute_updated_sample_price)
    - [`compute_committee_source_epoch`](#compute_committee_source_epoch)
    - [`batch_apply_participation_flag`](#batch_apply_participation_flag)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Updated `get_committee_count_per_slot`](#updated-get_committee_count_per_slot)
    - [`get_active_shard_count`](#get_active_shard_count)
    - [`get_shard_proposer_index`](#get_shard_proposer_index)
    - [`get_start_shard`](#get_start_shard)
    - [`compute_shard_from_committee_index`](#compute_shard_from_committee_index)
    - [`compute_committee_index_from_shard`](#compute_committee_index_from_shard)
  - [Block processing](#block-processing)
    - [Operations](#operations)
      - [Extended Attestation processing](#extended-attestation-processing)
      - [`process_shard_header`](#process_shard_header)
      - [`process_shard_proposer_slashing`](#process_shard_proposer_slashing)
  - [Epoch transition](#epoch-transition)
    - [`process_pending_shard_confirmations`](#process_pending_shard_confirmations)
    - [`reset_pending_shard_work`](#reset_pending_shard_work)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->


## Introduction

This document describes the extensions made to the Phase 0 design of The Beacon Chain to support data sharding,
based on the ideas [here](https://hackmd.io/G-Iy5jqyT7CXWEz8Ssos8g) and more broadly [here](https://arxiv.org/abs/1809.09044),
using KZG10 commitments to commit to data to remove any need for fraud proofs (and hence, safety-critical synchrony assumptions) in the design.

### Glossary

- **Data**: A list of KZG points, to translate a byte string into
- **Blob**: Data with commitments and meta-data, like a flattened bundle of L2 transactions.
- **Builder**: Independent actor that builds blobs and bids for proposal slots via fee-paying blob-headers, responsible for availability.
- **Shard proposer**: Validator taking bids from blob builders for shard data opportunity, co-signs with builder to propose the blob.

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `BLSCommitment` | `Bytes48` | A G1 curve point |
| `BLSFieldElement` | `uint256` | A number `x` in the range `0 <= x < MODULUS` |

## Constants

The following values are (non-configurable) constants used throughout the specification.

### Misc

| Name | Value | Notes |
| - | - | - |
| `PRIMITIVE_ROOT_OF_UNITY` | `7` | Primitive root of unity of the BLS12_381 (inner) modulus |
| `DATA_AVAILABILITY_INVERSE_CODING_RATE` | `2**1` (= 2) | Factor by which samples are extended for data availability encoding |
| `POINTS_PER_SAMPLE` | `uint64(2**4)` (= 16) | 31 * 16 = 496 bytes |
| `MODULUS` | `0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001` (curve order of BLS12_381) |

## Preset

### Misc

| Name | Value | Notes |
| - | - | - |
| `MAX_SHARDS` | `uint64(2**12)` (= 4,096) | Theoretical max shard count (used to determine data structure sizes) |
| `ACTIVE_SHARDS` | `uint64(2**8)` (= 256) | Initial shard count |
| `TARGET_SHARDS` | `uint64(ACTIVE_SHARDS // 2)` (= 256) | Initial shard count |
| `DATAGAS_PRICE_ADJUSTMENT_COEFFICIENT` | `uint64(2**3)` (= 8) | Sample price may decrease/increase by at most exp(1 / this value) *per epoch* |
| `SHARD_STATE_MEMORY_SLOTS` | `uint64(2**8)` (= 256) | Number of slots for which shard commitments and confirmation status is directly available in the state |

### Time parameters

With the introduction of intermediate blocks the number of slots per epoch is doubled (it counts beacon blocks and intermediate blocks).

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SLOTS_PER_EPOCH` | `uint64(2**6)` (= 64) | slots | 8:32 minutes |

### Shard blob samples

| Name | Value | Notes |
| - | - | - |
| `SAMPLES_PER_BLOB` | `uint64(2**9)` (= 2,048) | 248 * 2,048 = 507,904 bytes |

### Precomputed size verification points

| Name | Value |
| - | - |
| `G1_SETUP` | Type `List[G1]`. The G1-side trusted setup `[G, G*s, G*s**2....]`; note that the first point is the generator. |
| `G2_SETUP` | Type `List[G2]`. The G2-side trusted setup `[G, G*s, G*s**2....]` |
| `ROOT_OF_UNITY` | `pow(PRIMITIVE_ROOT_OF_UNITY, (MODULUS - 1) // int(SAMPLES_PER_BLOB * POINTS_PER_SAMPLE), MODULUS)` |

## Configuration

Note: Some preset variables may become run-time configurable for testnets, but default to a preset while the spec is unstable.  
E.g. `ACTIVE_SHARDS` and `SAMPLES_PER_BLOB`.

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SECONDS_PER_SLOT` | `uint64(8)` | seconds | 8 seconds |


## Updated containers

The following containers have updated definitions to support Sharding.

### `IntermediateBlockBid`

```python
class IntermediateBlockBid(Container):
    execution_payload_root: Root

    sharded_data_commitment: Root # Root of the sharded data (only data, not beacon/intermediate block commitments)

    sharded_data_commitments: uint64 # Count of sharded data commitments

    bid: Gwei # Block builder bid paid to proposer
    
    # Block builders use an Eth1 address -- need signature as
    # block builder fees and data gas base fees will be charged to this address
	signature_y_parity: bool
	signature_r: uint256
	signature_s: uint256    
```

### `BeaconBlockBody`

```python
class BeaconBlockBody(altair.BeaconBlockBody):  # Not from bellatrix because we don't want the payload
    intermediate_block_bid: IntermediateBlockBid
```

### `ShardedCommitmentsContainer`

```python
class ShardedCommitmentsContainer(Container):
    sharded_commitments: List[KZGCommitment, 2 * MAX_SHARDS]

    # Aggregate degree proof for all sharded_commitments
    degree_proof: KZGCommitment

    # The sizes of the blocks encoded in the commitments (last intermediate and all beacon blocks since)
    included_beacon_block_sizes: List[uint64, MAX_BEACON_BLOCKS_BETWEEN_INTERMEDIATE_BLOCKS + 1]
    
    # Number of commitments that are for sharded data (no blocks)
    included_sharded_data_commitments: uint64

    # Random evaluation of beacon blocks + execution payload (this helps with quick verification)
    block_verification_y: uint256
    block_verification_kzg_proof: KZGCommitment
```

### `IntermediateBlockBody`

```python
class IntermediateBlockBody(phase0.BeaconBlockBody):
    attestation: Attestation
    execution_payload: ExecutionPayload
    sharded_commitments_container: ShardedCommitmentsContainer
```

### `IntermediateBlockHeader`

```python
class IntermediateBlockHeader(Container):
    slot: Slot
    parent_root: Root
    state_root: Root
    body: Root
```

### `IntermediateBlock`

```python
class IntermediateBlock(Container):
    slot: Slot
    parent_root: Root
    state_root: Root
    body: IntermediateBlockBody
```

### `SignedIntermediateBlock`

```python
class SignedIntermediateBlock(Container):  # 
    message: IntermediateBlock

	signature_y_parity: bool
	signature_r: uint256
	signature_s: uint256    
```

### `SignedIntermediateBlockHeader`

```python
class SignedIntermediateBlockHeader(Container):  # 
    message: IntermediateBlockHeader

	signature_y_parity: bool
	signature_r: uint256
	signature_s: uint256    
```

### `BeaconState`

```python
class BeaconState(bellatrix.BeaconState):
    beacon_blocks_since_intermediate_block: List[BeaconBlock, MAX_BEACON_BLOCKS_BETWEEN_INTERMEDIATE_BLOCKS]
    last_intermediate_block: IntermediateBlock
```

### Beacon state accessors

#### `get_active_shard_count`

```python
def get_active_shard_count(state: BeaconState, epoch: Epoch) -> uint64:
    """
    Return the number of active shards.
    Note that this puts an upper bound on the number of committees per slot.
    """
    return ACTIVE_SHARDS
```

### Block processing

#### `process_beacon_block`

```python
def process_beacon_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)

    state.beacon_blocks_since_intermediate_block.append(block)
```

#### `process_intermediate_block`

```python
def process_intermediate_block(state: BeaconState, block: IntermediateBlock) -> None:
    process_intermediate_block_header(state, block)
    process_intermediate_block_bid_commitment(state, block)
    process_sharded_data(state, block)
    process_execution_payload(state, block.body.execution_payload, EXECUTION_ENGINE)
    process_intermediate_block_attestations(state, block)

    state.last_intermediate_block = block
```

#### Beacon Block Operations

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # Verify that outstanding deposits are processed up to the maximum number of deposits
    assert len(body.deposits) == min(MAX_DEPOSITS, state.eth1_data.deposit_count - state.eth1_deposit_index)

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)

    # New shard proposer slashing processing
    for_ops(body.shard_proposer_slashings, process_shard_proposer_slashing)

    # Limit is dynamic: based on active shard count
    assert len(body.shard_headers) <= MAX_SHARD_HEADERS_PER_SHARD * get_active_shard_count(state, get_current_epoch(state))
    for_ops(body.shard_headers, process_shard_header)

    # New attestation processing
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)
```

#### Intermediate Block Operations

```python
def process_intermediate_block_attestations(state: BeaconState, body: IntermediateBlockBody) -> None:

    for attestation in block.body.attestations:
    process_attestation(state, block.body.attestation)
```

#### Intermediate Block Bid Commitment

```python
def process_intermediate_block_bid_commitment(state: BeaconState, body: IntermediateBlockBody) -> None:
    # Get last intermediate block bid
    intermediate_block_bid = state.beacon_blocks_since_intermediate_block[-1].body.intermediate_block_bid

    assert intermediate_block_bid.execution_payload_root == hash_tree_root(body.execution_payload)

    assert intermediate_block_bid.sharded_data_commitments == body.sharded_commitments_container.included_sharded_data_commitments

    assert intermediate_block_bid.sharded_data_commitment == hash_tree_root(body.sharded_commitments_container.sharded_commitments[-intermediate_block_bid.sharded_data_commitments:])
```

#### Intermediate Block header

```python
def process_intermediate_block_header(state: BeaconState, block: BeaconBlock) -> None:
    # Verify that the slots match
    assert block.slot == state.slot

    # Verify that the block is newer than latest block header
    assert block.slot == state.latest_block_header.slot + 1

    # Verify that the parent matches
    assert block.parent_root == hash_tree_root(state.latest_block_header)

    # Cache current block as the new latest block
    # TODO! Adapt this to support intermediate block headers
    state.latest_block_header = BeaconBlockHeader(
        slot=block.slot,
        proposer_index=block.proposer_index,
        parent_root=block.parent_root,
        state_root=Bytes32(),  # Overwritten in the next process_slot call
        body_root=hash_tree_root(block.body),
    )
```

#### Sharded data


```python
def process_sharded_data(state: BeaconState, block: BeaconBlock) -> None:
    # Verify the degree proof

    # Verify that the 2*N commitments lie on a degree N-1 polynomial

    # Verify that last intermediate block has been included

    # Verify that beacon block (blocks if intermediate blocks were missing) have been included

```

The degree proof works as follows. For a block `B` with length `l` (so `l`  values in `[0...l - 1]`, seen as a polynomial `B(X)` which takes these values),
the length proof is the commitment to the polynomial `B(X) * X**(MAX_DEGREE + 1 - l)`,
where `MAX_DEGREE` is the maximum power of `s` available in the setup, which is `MAX_DEGREE = len(G2_SETUP) - 1`.
The goal is to ensure that a proof can only be constructed if `deg(B) < l` (there are not hidden higher-order terms in the polynomial, which would thwart reconstruction).

#### Execution payload

```python
def process_execution_payload(state: BeaconState, payload: ExecutionPayload, execution_engine: ExecutionEngine) -> None:
    # Verify consistency of the parent hash with respect to the previous execution payload header
    if is_merge_transition_complete(state):
        assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify random
    assert payload.random == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)

    # Get sharded data headers

    # Get all unprocessed intermediate block bids


    # Verify the execution payload is valid
    assert execution_engine.execute_payload(payload)
    # Cache execution payload header
    state.latest_execution_payload_header = ExecutionPayloadHeader(
        parent_hash=payload.parent_hash,
        fee_recipient=payload.fee_recipient,
        state_root=payload.state_root,
        receipt_root=payload.receipt_root,
        logs_bloom=payload.logs_bloom,
        random=payload.random,
        block_number=payload.block_number,
        gas_limit=payload.gas_limit,
        gas_used=payload.gas_used,
        timestamp=payload.timestamp,
        extra_data=payload.extra_data,
        base_fee_per_gas=payload.base_fee_per_gas,
        block_hash=payload.block_hash,
        transactions_root=hash_tree_root(payload.transactions),
    )
```

### Epoch transition

This epoch transition overrides Bellatrix epoch transition:

```python
def process_epoch(state: BeaconState) -> None:
    # Base functionality
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_roots_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
```
