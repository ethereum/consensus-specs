# Sharding -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
  - [Glossary](#glossary)
- [Constants](#constants)
  - [Misc](#misc)
  - [Domain types](#domain-types)
- [Preset](#preset)
  - [Misc](#misc-1)
  - [Time parameters](#time-parameters)
  - [Shard blob samples](#shard-blob-samples)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters-1)
- [Containers](#containers)
  - [New Containers](#new-containers)
    - [`BuilderBlockBid`](#builderblockbid)
    - [`BuilderBlockBidWithRecipientAddress`](#builderblockbidwithrecipientaddress)
    - [`ShardedCommitmentsContainer`](#shardedcommitmentscontainer)
    - [`ShardSample`](#shardsample)
  - [Modified containers](#modified-containers)
    - [`BeaconState`](#beaconstate)
    - [`BuilderBlockData`](#builderblockdata)
    - [`BeaconBlockBody`](#beaconblockbody)
- [Helper functions](#helper-functions)
  - [Block processing](#block-processing)
    - [`is_builder_block_slot`](#is_builder_block_slot)
  - [Beacon state accessors](#beacon-state-accessors)
    - [`get_active_shard_count`](#get_active_shard_count)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing-1)
    - [`process_block`](#process_block)
    - [Block header](#block-header)
    - [Builder Block Bid](#builder-block-bid)
    - [Sharded data](#sharded-data)
    - [Execution payload](#execution-payload)

<!-- mdformat-toc end -->

## Introduction

This document describes the extensions made to the Phase 0 design of The Beacon Chain to support data sharding,
based on the ideas [here](https://notes.ethereum.org/@dankrad/new_sharding) and more broadly [here](https://arxiv.org/abs/1809.09044),
using KZG10 commitments to commit to data to remove any need for fraud proofs (and hence, safety-critical synchrony assumptions) in the design.

### Glossary

- **Data**: A list of KZG points, to translate a byte string into
- **Blob**: Data with commitments and meta-data, like a flattened bundle of L2 transactions.

## Constants

The following values are (non-configurable) constants used throughout the specification.

### Misc

| Name | Value | Notes |
| - | - | - |
| `FIELD_ELEMENTS_PER_SAMPLE` | `uint64(2**4)` (= 16) | 31 * 16 = 496 bytes |

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_SHARD_SAMPLE` | `DomainType('0x10000000')` |

## Preset

### Misc

| Name | Value | Notes |
| - | - | - |
| `MAX_SHARDS` | `uint64(2**12)` (= 4,096) | Theoretical max shard count (used to determine data structure sizes) |
| `ACTIVE_SHARDS` | `uint64(2**8)` (= 256) | Initial shard count |
| `MAX_PROPOSER_BLOCKS_BETWEEN_BUILDER_BLOCKS` | `uint64(2**4)` (= 16) | TODO: Need to define what happens if there were more blocks without builder blocks |

### Time parameters

With the introduction of builder blocks the number of slots per epoch is doubled (it counts beacon blocks and builder blocks).

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SLOTS_PER_EPOCH` | `uint64(2**6)` (= 64) | slots | 8:32 minutes |

### Shard blob samples

| Name | Value | Notes |
| - | - | - |
| `SAMPLES_PER_BLOB` | `uint64(2**9)` (= 512) | 248 * 512 = 126,976 bytes |

## Configuration

*Note*: Some preset variables may become run-time configurable for testnets, but default to a preset while the spec is unstable.
E.g. `ACTIVE_SHARDS` and `SAMPLES_PER_BLOB`.

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SECONDS_PER_SLOT` | `uint64(8)` | seconds | 8 seconds |

## Containers

### New Containers

#### `BuilderBlockBid`

```python
class BuilderBlockBid(Container):
    slot: Slot
    parent_block_root: Root

    execution_payload_root: Root

    sharded_data_commitment_root: Root # Root of the sharded data (only data, not beacon/builder block commitments)

    sharded_data_commitment_count: uint64 # Count of sharded data commitments

    bid: Gwei # Block builder bid paid to proposer

    validator_index: ValidatorIndex # Validator index for this bid

    # Block builders use an Eth1 address -- need signature as
    # block bid and data gas base fees will be charged to this address
    signature_y_parity: bool
    signature_r: uint256
    signature_s: uint256
```

#### `BuilderBlockBidWithRecipientAddress`

```python
class BuilderBlockBidWithRecipientAddress(Container):
    builder_block_bid: Union[None, BuilderBlockBid]
    recipient_address: ExecutionAddress # Address to receive the block builder bid
```

#### `ShardedCommitmentsContainer`

```python
class ShardedCommitmentsContainer(Container):
    sharded_commitments: List[KZGCommitment, 2 * MAX_SHARDS]

    # Aggregate degree proof for all sharded_commitments
    degree_proof: KZGCommitment

    # The sizes of the blocks encoded in the commitments (last builder and all beacon blocks since)
    included_block_sizes: List[uint64, MAX_PROPOSER_BLOCKS_BETWEEN_BUILDER_BLOCKS + 1]

    # Number of commitments that are for sharded data (no blocks)
    included_sharded_data_commitments: uint64

    # Random evaluation of beacon blocks + execution payload (this helps with quick verification)
    block_verification_kzg_proof: KZGCommitment
```

#### `ShardSample`

```python
class ShardSample(Container):
    slot: Slot
    row: uint64
    column: uint64
    data: Vector[BLSFieldElement, FIELD_ELEMENTS_PER_SAMPLE]
    proof: KZGCommitment
    builder: ValidatorIndex
    signature: BLSSignature
```

### Modified containers

#### `BeaconState`

```python
class BeaconState(bellatrix.BeaconState):
    blocks_since_builder_block: List[BeaconBlock, MAX_PROPOSER_BLOCKS_BETWEEN_BUILDER_BLOCKS]
```

#### `BuilderBlockData`

```python
class BuilderBlockData(Container):
    execution_payload: ExecutionPayload
    sharded_commitments_container: ShardedCommitmentsContainer
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(altair.BeaconBlockBody):
    payload_data: Union[BuilderBlockBid, BuilderBlockData]
```

## Helper functions

### Block processing

#### `is_builder_block_slot`

```python
def is_builder_block_slot(slot: Slot) -> bool:
    return slot % 2 == 1
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

## Beacon chain state transition function

### Block processing

#### `process_block`

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    verify_builder_block_bid(state, block)
    process_sharded_data(state, block)
    process_execution_payload(state, block, EXECUTION_ENGINE)

    if not is_builder_block_slot(block.slot):
        process_randao(state, block.body)

    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)

    if is_builder_block_slot(block.slot):
        state.blocks_since_builder_block = []
    state.blocks_since_builder_block.append(block)
```

#### Block header

```python
def process_block_header(state: BeaconState, block: BeaconBlock) -> None:
    # Verify that the slots match
    assert block.slot == state.slot
    # Verify that the block is newer than latest block header
    assert block.slot > state.latest_block_header.slot
    # Verify that proposer index is the correct index
    if not is_builder_block_slot(block.slot):
        assert block.proposer_index == get_beacon_proposer_index(state)
    # Verify that the parent matches
    assert block.parent_root == hash_tree_root(state.latest_block_header)
    # Cache current block as the new latest block
    state.latest_block_header = BeaconBlockHeader(
        slot=block.slot,
        proposer_index=block.proposer_index,
        parent_root=block.parent_root,
        state_root=Bytes32(),  # Overwritten in the next process_slot call
        body_root=hash_tree_root(block.body),
    )

    # Verify proposer is not slashed
    proposer = state.validators[block.proposer_index]
    assert not proposer.slashed
```

#### Builder Block Bid

```python
def verify_builder_block_bid(state: BeaconState, block: BeaconBlock) -> None:
    if is_builder_block_slot(block.slot):
        # Get last builder block bid
        assert state.blocks_since_builder_block[-1].body.payload_data.selector == 0
        builder_block_bid = state.blocks_since_builder_block[-1].body.payload_data.value.builder_block_bid
        assert builder_block_bid.slot + 1 == block.slot

        assert block.body.payload_data.selector == 1 # Verify that builder block does not contain bid

        builder_block_data = block.body.payload_data.value

        assert builder_block_bid.execution_payload_root == hash_tree_root(builder_block_data.execution_payload)

        assert builder_block_bid.sharded_data_commitment_count == builder_block_data.included_sharded_data_commitments

        assert builder_block_bid.sharded_data_commitment_root == hash_tree_root(builder_block_data.sharded_commitments[-builder_block_bid.included_sharded_data_commitments:])

        assert builder_block_bid.validator_index == block.proposer_index

    else:
        assert block.body.payload_data.selector == 0

        builder_block_bid = block.body.payload_data.value.builder_block_bid
        assert builder_block_bid.slot == block.slot
        assert builder_block_bid.parent_block_root == block.parent_root
        # We do not check that the builder address exists or has sufficient balance here.
        # If it does not have sufficient balance, the block proposer loses out, so it is their
        # responsibility to check.

        # Check that the builder is a slashable validator. We can probably reduce this requirement and only
        # ensure that they have 1 ETH in their account as a DOS protection.
        builder = state.validators[builder_block_bid.validator_index]
        assert is_slashable_validator(builder, get_current_epoch(state))
```

#### Sharded data

```python
def process_sharded_data(state: BeaconState, block: BeaconBlock) -> None:
    if is_builder_block_slot(block.slot):
        assert block.body.payload_data.selector == 1
        sharded_commitments_container = block.body.payload_data.value.sharded_commitments_container

        # Verify not too many commitments
        assert len(sharded_commitments_container.sharded_commitments) // 2 <= get_active_shard_count(state, get_current_epoch(state))

        # Verify the degree proof
        r = hash_to_bls_field(sharded_commitments_container.sharded_commitments, 0)
        r_powers = compute_powers(r, len(sharded_commitments_container.sharded_commitments))
        combined_commitment = elliptic_curve_lincomb(sharded_commitments_container.sharded_commitments, r_powers)

        payload_field_elements_per_blob = SAMPLES_PER_BLOB * FIELD_ELEMENTS_PER_SAMPLE // 2

        verify_degree_proof(combined_commitment, payload_field_elements_per_blob, sharded_commitments_container.degree_proof)

        # Verify that the 2*N commitments lie on a degree < N polynomial
        low_degree_check(sharded_commitments_container.sharded_commitments)

        # Verify that blocks since the last builder block have been included
        blocks_chunked = [bytes_to_field_elements(ssz_serialize(block)) for block in state.blocks_since_builder_block]
        block_vectors = []

        for block_chunked in blocks_chunked:
            for i in range(0, len(block_chunked), payload_field_elements_per_blob):
                block_vectors.append(block_chunked[i:i + payload_field_elements_per_blob])

        number_of_blobs = len(block_vectors)
        r = hash_to_bls_field(sharded_commitments_container.sharded_commitments[:number_of_blobs], 0)
        x = hash_to_bls_field(sharded_commitments_container.sharded_commitments[:number_of_blobs], 1)

        r_powers = compute_powers(r, number_of_blobs)
        combined_vector = vector_lincomb(block_vectors, r_powers)
        combined_commitment = elliptic_curve_lincomb(sharded_commitments_container.sharded_commitments[:number_of_blobs], r_powers)
        y = evaluate_polynomial_in_evaluation_form(combined_vector, x)

        verify_kzg_proof(combined_commitment, x, y, sharded_commitments_container.block_verification_kzg_proof)

        # Verify that number of sharded data commitments is correctly indicated
        assert 2 * (number_of_blobs + included_sharded_data_commitments) == len(sharded_commitments_container.sharded_commitments)
```

#### Execution payload

```python
def process_execution_payload(state: BeaconState, block: BeaconBlock, execution_engine: ExecutionEngine) -> None:
    if is_builder_block_slot(block.slot):
        assert block.body.payload_data.selector == 1
        payload = block.body.payload_data.value.execution_payload

        # Verify consistency of the parent hash with respect to the previous execution payload header
        assert payload.parent_hash == state.latest_execution_payload_header.block_hash
        # Verify random
        assert payload.random == get_randao_mix(state, get_current_epoch(state))
        # Verify timestamp
        assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)

        # Get sharded data commitments
        sharded_commitments_container = block.body.sharded_commitments_container
        sharded_data_commitments = sharded_commitments_container.sharded_commitments[-sharded_commitments_container.included_sharded_data_commitments:]

        # Get all unprocessed builder block bids
        unprocessed_builder_block_bid_with_recipient_addresses = []
        for block in state.blocks_since_builder_block[1:]:
            unprocessed_builder_block_bid_with_recipient_addresses.append(block.body.builder_block_bid_with_recipient_address.value)

        # Verify the execution payload is valid
        # The execution engine gets two extra payloads: One for the sharded data commitments (these are needed to verify type 3 transactions)
        # and one for all so far unprocessed builder block bids:
        # * The execution engine needs to transfer the balance from the bidder to the proposer.
        # * The execution engine needs to deduct data gas fees from the bidder balances
        assert execution_engine.execute_payload(payload,
                                                sharded_data_commitments,
                                                unprocessed_builder_block_bid_with_recipient_addresses)

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