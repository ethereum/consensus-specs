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
- [Preset](#preset)
  - [Misc](#misc-1)
  - [Time parameters](#time-parameters)
  - [Shard blob samples](#shard-blob-samples)
  - [Precomputed size verification points](#precomputed-size-verification-points)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters-1)
- [Containers](#containers)
  - [New Containers](#new-containers)
    - [`IntermediateBlockBid`](#intermediateblockbid)
    - [`IntermediateBlockBidWithRecipientAddress`](#intermediateblockbidwithrecipientaddress)
    - [`ShardedCommitmentsContainer`](#shardedcommitmentscontainer)
  - [Extended Containers](#extended-containers)
    - [`BeaconState`](#beaconstate)
    - [`BeaconBlockBody`](#beaconblockbody)
- [Helper functions](#helper-functions)
  - [Block processing](#block-processing)
    - [`is_intermediate_block_slot`](#is_intermediate_block_slot)
  - [KZG](#kzg)
    - [`hash_to_field`](#hash_to_field)
    - [`compute_powers`](#compute_powers)
    - [`verify_kzg_proof`](#verify_kzg_proof)
    - [`verify_degree_proof`](#verify_degree_proof)
    - [`block_to_field_elements`](#block_to_field_elements)
    - [`roots_of_unity`](#roots_of_unity)
    - [`modular_inverse`](#modular_inverse)
    - [`eval_poly_at`](#eval_poly_at)
    - [`next_power_of_two`](#next_power_of_two)
    - [`low_degree_check`](#low_degree_check)
    - [`vector_lincomb`](#vector_lincomb)
    - [`elliptic_curve_lincomb`](#elliptic_curve_lincomb)
  - [Beacon state accessors](#beacon-state-accessors)
    - [`get_active_shard_count`](#get_active_shard_count)
  - [Block processing](#block-processing-1)
    - [`process_block`](#process_block)
    - [Block header](#block-header)
    - [Intermediate Block Bid](#intermediate-block-bid)
    - [Sharded data](#sharded-data)
    - [Execution payload](#execution-payload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->


## Introduction

This document describes the extensions made to the Phase 0 design of The Beacon Chain to support data sharding,
based on the ideas [here](https://notes.ethereum.org/@dankrad/new_sharding) and more broadly [here](https://arxiv.org/abs/1809.09044),
using KZG10 commitments to commit to data to remove any need for fraud proofs (and hence, safety-critical synchrony assumptions) in the design.

### Glossary

- **Data**: A list of KZG points, to translate a byte string into
- **Blob**: Data with commitments and meta-data, like a flattened bundle of L2 transactions.

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `KZGCommitment` | `Bytes48` | A G1 curve point |
| `BLSFieldElement` | `uint256` | A number `x` in the range `0 <= x < MODULUS` |

## Constants

The following values are (non-configurable) constants used throughout the specification.

### Misc

| Name | Value | Notes |
| - | - | - |
| `PRIMITIVE_ROOT_OF_UNITY` | `7` | Primitive root of unity of the BLS12_381 (inner) modulus |
| `DATA_AVAILABILITY_INVERSE_CODING_RATE` | `2**1` (= 2) | Factor by which samples are extended for data availability encoding |
| `FIELD_ELEMENTS_PER_SAMPLE` | `uint64(2**4)` (= 16) | 31 * 16 = 496 bytes |
| `MODULUS` | `0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001` (curve order of BLS12_381) |

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_SHARD_SAMPLE`     | `DomainType('0x10000000')` |

## Preset

### Misc

| Name | Value | Notes |
| - | - | - |
| `MAX_SHARDS` | `uint64(2**12)` (= 4,096) | Theoretical max shard count (used to determine data structure sizes) |
| `ACTIVE_SHARDS` | `uint64(2**8)` (= 256) | Initial shard count |

### Time parameters

With the introduction of intermediate blocks the number of slots per epoch is doubled (it counts beacon blocks and intermediate blocks).

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SLOTS_PER_EPOCH` | `uint64(2**6)` (= 64) | slots | 8:32 minutes |

### Shard blob samples

| Name | Value | Notes |
| - | - | - |
| `SAMPLES_PER_BLOB` | `uint64(2**9)` (= 512) | 248 * 512 = 126,976 bytes |

### Precomputed size verification points

| Name | Value |
| - | - |
| `G1_SETUP` | Type `List[G1]`. The G1-side trusted setup `[G, G*s, G*s**2....]`; note that the first point is the generator. |
| `G2_SETUP` | Type `List[G2]`. The G2-side trusted setup `[G, G*s, G*s**2....]` |
| `ROOT_OF_UNITY` | `pow(PRIMITIVE_ROOT_OF_UNITY, (MODULUS - 1) // int(SAMPLES_PER_BLOB * FIELD_ELEMENTS_PER_SAMPLE), MODULUS)` |

## Configuration

Note: Some preset variables may become run-time configurable for testnets, but default to a preset while the spec is unstable.  
E.g. `ACTIVE_SHARDS` and `SAMPLES_PER_BLOB`.

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SECONDS_PER_SLOT` | `uint64(8)` | seconds | 8 seconds |


## Containers

### New Containers

#### `IntermediateBlockBid`

```python
class IntermediateBlockBid(Container):
    slot: Slot
    parent_block_root: Root

    execution_payload_root: Root

    sharded_data_commitment_root: Root # Root of the sharded data (only data, not beacon/intermediate block commitments)

    sharded_data_commitment_count: uint64 # Count of sharded data commitments

    bid: Gwei # Block builder bid paid to proposer

    validator_index: ValidatorIndex # Validator index for this bid
    
    # Block builders use an Eth1 address -- need signature as
    # block builder fees and data gas base fees will be charged to this address
	signature_y_parity: bool
	signature_r: uint256
	signature_s: uint256    
```

#### `IntermediateBlockBidWithRecipientAddress`

```python
class IntermediateBlockBidWithRecipientAddress(Container):
    intermediate_block_bid: Union[None, IntermediateBlockBid]
    ethereum_address: Bytes[20] # Address to receive the block builder bid
```

#### `ShardedCommitmentsContainer`

```python
class ShardedCommitmentsContainer(Container):
    sharded_commitments: List[KZGCommitment, 2 * MAX_SHARDS]

    # Aggregate degree proof for all sharded_commitments
    degree_proof: KZGCommitment

    # The sizes of the blocks encoded in the commitments (last intermediate and all beacon blocks since)
    included_block_sizes: List[uint64, MAX_BEACON_BLOCKS_BETWEEN_INTERMEDIATE_BLOCKS + 1]
    
    # Number of commitments that are for sharded data (no blocks)
    included_sharded_data_commitments: uint64

    # Random evaluation of beacon blocks + execution payload (this helps with quick verification)
    block_verification_kzg_proof: KZGCommitment
```

#### `SignedShardSample`

```python
class SignedShardSample(Container):
    slot: Slot
    row: uint64
    column: uint64
    data: Vector[BLSFieldElement, FIELD_ELEMENTS_PER_SAMPLE]
    proof: KZGCommitment
    builder: ValidatorIndex
    signature: BLSSignature
```

### Extended Containers

#### `BeaconState`

```python
class BeaconState(bellatrix.BeaconState):
    blocks_since_intermediate_block: List[BeaconBlock, MAX_BEACON_BLOCKS_BETWEEN_INTERMEDIATE_BLOCKS]
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(bellatrix.BeaconBlockBody):
    execution_payload: Union[None, ExecutionPayload]
    sharded_commitments_container: Union[None, ShardedCommitmentsContainer]
    intermediate_block_bid_with_recipient_address: Union[None, IntermediateBlockBidWithRecipientAddress]
```

## Helper functions

*Note*: The definitions below are for specification purposes and are not necessarily optimal implementations.

### Block processing

#### `is_intermediate_block_slot`

```python
def is_intermediate_block_slot(slot: Slot):
    return slot % 2 == 1
```

### KZG

#### `hash_to_field`

```python
def hash_to_field(x: Container):
    return int.from_bytes(hash_tree_root(x), "little") % MODULUS
```

#### `compute_powers`

```python
def compute_powers(x: BLSFieldElement, n: uint64) -> List[BLSFieldElement]:
    current_power = 1
    powers = []
    for i in range(n):
        powers.append(BLSFieldElement(current_power))
        current_power = current_power * int(x) % MODULUS
    return powers
```

#### `verify_kzg_proof`

```python
def verify_kzg_proof(commitment: KZGCommitment, x: BLSFieldElement, y: BLSFieldElement, proof: KZGCommitment) -> None:
    zero_poly = G2_SETUP[1].add(G2_SETUP[0].mult(x).neg())

    assert (
        bls.Pairing(proof, zero_poly)
        == bls.Pairing(commitment.add(G1_SETUP[0].mult(y).neg), G2_SETUP[0])
    )
```

#### `interpolate_poly`

```python
def interpolate_poly(xs: List[BLSFieldElement], ys: List[BLSFieldElement]):
    """
    Lagrange interpolation
    """
    # TODO!
```

#### `verify_kzg_multiproof`

```python
def verify_kzg_multiproof(commitment: KZGCommitment, xs: List[BLSFieldElement], ys: List[BLSFieldElement], proof: KZGCommitment) -> None:
    zero_poly = elliptic_curve_lincomb(G2_SETUP[:len(xs)], interpolate_poly(xs, [0] * len(ys)))
    interpolated_poly = elliptic_curve_lincomb(G2_SETUP[:len(xs)], interpolate_poly(xs, ys))

    assert (
        bls.Pairing(proof, zero_poly)
        == bls.Pairing(commitment.add(interpolated_poly.neg()), G2_SETUP[0])
    )
```

#### `verify_degree_proof`

```python
def verify_degree_proof(commitment: KZGCommitment, degree: uint64, proof: KZGCommitment):
    """
    Verifies that the commitment is of polynomial degree <= degree. 
    """

    assert (
        bls.Pairing(proof, G2_SETUP[0])
        == bls.Pairing(commitment, G2_SETUP[-degree - 1])
    )
```

#### `block_to_field_elements`

```python
def block_to_field_elements(block: bytes) -> List[BLSFieldElement]:
    """
    Slices a block into 31 byte chunks that can fit into field elements
    """
    sliced_block = [block[i:i + 31] for i in range(0, len(bytes), 31)]
    return [BLSFieldElement(int.from_bytes(x, "little")) for x in sliced_block]
```

#### `roots_of_unity`

```python
def roots_of_unity(order: uint64) -> List[BLSFieldElement]:
    r = []
    root_of_unity = pow(PRIMITIVE_ROOT_OF_UNITY, (MODULUS - 1) // order, MODULUS)

    current_root_of_unity = 1
    for i in range(len(SAMPLES_PER_BLOB * FIELD_ELEMENTS_PER_SAMPLE)):
        r.append(current_root_of_unity)
        current_root_of_unity = current_root_of_unity * root_of_unity % MODULUS
    return r
```

#### `modular_inverse`

```python
def modular_inverse(a):
    assert(a == 0):
    lm, hm = 1, 0
    low, high = a % MODULUS, MODULUS
    while low > 1:
        r = high // low
        nm, new = hm - lm * r, high - low * r
        lm, low, hm, high = nm, new, lm, low
    return lm % MODULUS
```

#### `eval_poly_at`

```python
def eval_poly_at(poly: List[BLSFieldElement], x: BLSFieldElement) -> BLSFieldElement:
    """
    Evaluates a polynomial (in evaluation form) at an arbitrary point
    """
    field_elements_per_blob = SAMPLES_PER_BLOB * FIELD_ELEMENTS_PER_SAMPLE
    roots = roots_of_unity(field_elements_per_blob)

    def A(z):
        r = 1
        for w in roots:
            r = r * (z - w) % MODULUS
        return r

    def Aprime(z):
        return field_elements_per_blob * pow(z, field_elements_per_blob - 1, MODULUS) 

    r = 0
    inverses = [modular_inverse(z - x) for z in roots]
    for i, x in enumerate(inverses):
        r += f[i] * modular_inverse(Aprime(roots[i])) * x % self.MODULUS
    r = r * A(x) % self.MODULUS
    return r
```

#### `next_power_of_two`

```python
def next_power_of_two(x: int) -> int:
    return 2 ** ((x - 1).bit_length())
```

#### `low_degree_check`

```python
def low_degree_check(commitments: List[KZGCommitment]):
    """
    Checks that the commitments are on a low-degree polynomial
    If there are 2*N commitments, that means they should lie on a polynomial
    of degree d = K - N - 1, where K = next_power_of_two(2*N)
    (The remaining positions are filled with 0, this is to make FFTs usable)

    For details see here: https://notes.ethereum.org/@dankrad/barycentric_low_degree_check
    """
    assert len(commitments) % 2 == 0
    N = len(commitments) // 2
    r = hash_to_field(commitments)
    K = next_power_of_two(2 * N)
    d = K - N - 1
    r_to_K = pow(r, N, K)
    roots = roots_of_unity(K)

    # For an efficient implementation, B and Bprime should be precomputed
    def B(z):
        r = 1
        for w in roots[:d + 1]:
            r = r * (z - w) % MODULUS
        return r

    def Bprime(z):
        r = 0
        for i in range(d + 1):
            m = 1
            for w in roots[:i] + roots[i+1:d + 1]:
                m = m * (z - w) % MODULUS
            r = (r + M) % MODULUS
        return r

    coefs = []
    for i in range(K):
        coefs.append( - (r_to_K - 1) * modular_inverse(K * roots[i * (K - 1) % K] * (r - roots[i])) % MODULUS)
    for i in range(d + 1):
        coefs[i] = (coefs[i] + B(r) * modular_inverse(Bprime(r) * (r - roots[i]))) % MODULUS
    
    assert elliptic_curve_lincomb(commitments, coefs) == bls.Z1()
```

#### `vector_lincomb`

```python
def vector_lincomb(vectors: List[List[BLSFieldElement]], scalars: List[BLSFieldElement]) -> List[BLSFieldElement]:
    """
    Compute a linear combination of field element vectors
    """
    r = [0 for i in len(vectors[0])]
    for v, a in zip(vectors, scalars):
        for i, x in enumerate(v):
            r[i] = (r[i] + a * x) % MODULUS
    return [BLSFieldElement(x) for x in r]
```

#### `elliptic_curve_lincomb`

```python
def elliptic_curve_lincomb(points: List[KZGCommitment], scalars: List[BLSFieldElement]) -> KZGCommitment:
    """
    BLS multiscalar multiplication. This function can be optimized using Pippenger's algorithm and variants. This is a non-optimized implementation.
    """
    r = bls.Z1()
    for x, a in zip(points, scalars):
        r = r.add(x.mult(a))
    return r
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

#### `process_block`

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    verify_intermediate_block_bid(state, block)
    process_sharded_data(state, block)
    if is_execution_enabled(state, block.body):
        process_execution_payload(state, block, EXECUTION_ENGINE)

    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)

    if is_intermediate_block_slot(block.slot):
        state.blocks_since_intermediate_block = []
    state.blocks_since_intermediate_block.append(block)
```

#### Block header

```python
def process_block_header(state: BeaconState, block: BeaconBlock) -> None:
    # Verify that the slots match
    assert block.slot == state.slot
    # Verify that the block is newer than latest block header
    assert block.slot > state.latest_block_header.slot
    # Verify that proposer index is the correct index
    if not is_intermediate_block_slot(block.slot):
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

#### Intermediate Block Bid

```python
def verify_intermediate_block_bid(state: BeaconState, block: BeaconBlock) -> None:
    if is_intermediate_block_slot(block.slot):
        # Get last intermediate block bid
        assert state.blocks_since_intermediate_block[-1].body.intermediate_block_bid_with_recipient_address.selector == 1
        intermediate_block_bid = state.blocks_since_intermediate_block[-1].body.intermediate_block_bid_with_recipient_address.value.intermediate_block_bid
        assert intermediate_block_bid.slot + 1 == block.slot

        assert intermediate_block_bid.execution_payload_root == hash_tree_root(block.body.execution_payload)

        assert intermediate_block_bid.sharded_data_commitment_count == block.body.sharded_commitments_container.included_sharded_data_commitments

        assert intermediate_block_bid.sharded_data_commitment_root == hash_tree_root(block.body.sharded_commitments_container.sharded_commitments[-intermediate_block_bid.sharded_data_commitments:])

        assert intermediate_block_bid.validator_index == block.proposer_index

        assert block.body.intermediate_block_bid_with_recipient_address.selector == 0 # Verify that intermediate block does not contain bid
    else:
        assert block.body.intermediate_block_bid_with_recipient_address.selector == 1

        intermediate_block_bid = block.body.intermediate_block_bid_with_recipient_address.value.intermediate_block_bid
        assert intermediate_block_bid.slot == block.slot
        assert intermediate_block_bid.parent_block_root == block.parent_root
```

#### Sharded data

```python
def process_sharded_data(state: BeaconState, block: BeaconBlock) -> None:
    if is_intermediate_block_slot(block.slot):
        assert block.body.sharded_commitments_container.selector == 1
        sharded_commitments_container = block.body.sharded_commitments_container.value

        # Verify not too many commitments
        assert len(sharded_commitments_container.sharded_commitments) // 2 <= get_active_shard_count(state, get_current_epoch(state))

        # Verify the degree proof
        r = hash_to_field(sharded_commitments_container.sharded_commitments)
        r_powers = compute_powers(r, len(sharded_commitments_container.sharded_commitments))
        combined_commitment = elliptic_curve_lincomb(sharded_commitments_container.sharded_commitments, r_powers)

        verify_degree_proof(combined_commitment, SAMPLES_PER_BLOB * FIELD_ELEMENTS_PER_SAMPLE, sharded_commitments_container.degree_proof)

        # Verify that the 2*N commitments lie on a degree < N polynomial
        low_degree_check(sharded_commitments_container.sharded_commitments)

        # Verify that blocks since the last intermediate block have been included
        blocks_chunked = [block_to_field_elements(ssz_serialize(block)) for block in state.blocks_since_intermediate_block]
        block_vectors = []
        field_elements_per_blob = SAMPLES_PER_BLOB * FIELD_ELEMENTS_PER_SAMPLE
        for block_chunked in blocks_chunked:
            for i in range(0, len(block_chunked), field_elements_per_blob):
                block_vectors.append(block_chunked[i:i + field_elements_per_blob])
            
        number_of_blobs = len(block_vectors)
        r = hash_to_field([sharded_commitments_container.sharded_commitments[:number_of_blobs], 0])
        x = hash_to_field([sharded_commitments_container.sharded_commitments[:number_of_blobs], 1])

        r_powers = compute_powers(r, number_of_blobs)
        combined_vector = vector_lincomb(block_vectors, r_powers)
        combined_commitment = elliptic_curve_lincomb(sharded_commitments_container.sharded_commitments[:number_of_blobs], r_powers)
        y = eval_poly_at(combined_vector, x)

        verify_kzg_proof(combined_commitment, x, y, block_verification_kzg_proof)

        # Verify that number of sharded data commitments is correctly indicated
        assert 2 * (number_of_blobs + included_sharded_data_commitments) == len(sharded_commitments_container.sharded_commitments)

    else:
        assert block.body.sharded_commitments_container.selector == 0 # Only intermediate blocks have sharded commitments
```

#### Execution payload

```python
def process_execution_payload(state: BeaconState, block: BeaconBlock, execution_engine: ExecutionEngine) -> None:
    if is_intermediate_block_slot(block.slot):
        assert block.body.execution_payload.selector == 1
        payload = block.body.execution_payload.value

        # Verify consistency of the parent hash with respect to the previous execution payload header
        if is_merge_transition_complete(state):
            assert payload.parent_hash == state.latest_execution_payload_header.block_hash
        # Verify random
        assert payload.random == get_randao_mix(state, get_current_epoch(state))
        # Verify timestamp
        assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)

        # Get sharded data commitments
        sharded_commitments_container = block.body.sharded_commitments_container
        sharded_data_commitments = sharded_commitments_container.sharded_commitments[-sharded_commitments_container.included_sharded_data_commitments:]

        # Get all unprocessed intermediate block bids
        unprocessed_intermediate_block_bid_with_recipient_addresses = []
        for block in state.blocks_since_intermediate_block[1:]:
            unprocessed_intermediate_block_bid_with_recipient_addresses.append(block.body.intermediate_block_bid_with_recipient_address.value)

        # Verify the execution payload is valid
        # The execution engine gets two extra payloads: One for the sharded data commitments (these are needed to verify type 3 transactions)
        # and one for all so far unprocessed intermediate block bids:
        # * The execution engine needs to transfer the balance from the bidder to the proposer.
        # * The execution engine needs to deduct data gas fees from the bidder balances
        assert execution_engine.execute_payload(payload,
                                                sharded_data_commitments,
                                                unprocessed_intermediate_block_bid_with_recipient_addresses)

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
    else:
        assert block.body.execution_payload.selector == 0 # Only intermediate blocks have execution payloads
```