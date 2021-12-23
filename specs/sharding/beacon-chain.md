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
| `Shard` | `uint64` | A shard number |
| `BLSCommitment` | `Bytes48` | A G1 curve point |
| `BLSPoint` | `uint256` | A number `x` in the range `0 <= x < MODULUS` |
| `BuilderIndex` | `uint64` | Builder registry index |

## Constants

The following values are (non-configurable) constants used throughout the specification.

### Misc

| Name | Value | Notes |
| - | - | - |
| `PRIMITIVE_ROOT_OF_UNITY` | `7` | Primitive root of unity of the BLS12_381 (inner) modulus |
| `DATA_AVAILABILITY_INVERSE_CODING_RATE` | `2**1` (= 2) | Factor by which samples are extended for data availability encoding |
| `POINTS_PER_SAMPLE` | `uint64(2**3)` (= 8) | 31 * 8 = 248 bytes |
| `MODULUS` | `0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001` (curve order of BLS12_381) |

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_SHARD_BLOB` | `DomainType('0x80000000')` |

### Shard Work Status

| Name | Value | Notes |
| - | - | - |
| `SHARD_WORK_UNCONFIRMED` | `0` | Unconfirmed, nullified after confirmation time elapses |
| `SHARD_WORK_CONFIRMED` | `1` | Confirmed, reduced to just the commitment |
| `SHARD_WORK_PENDING` | `2` | Pending, a list of competing headers |

### Misc

TODO: `PARTICIPATION_FLAG_WEIGHTS` backwards-compatibility is difficult, depends on usage.

| Name | Value |
| - | - |
| `PARTICIPATION_FLAG_WEIGHTS` | `[TIMELY_SOURCE_WEIGHT, TIMELY_TARGET_WEIGHT, TIMELY_HEAD_WEIGHT, TIMELY_SHARD_WEIGHT]` |

### Participation flag indices

| Name | Value |
| - | - |
| `TIMELY_SHARD_FLAG_INDEX` | `3` |

### Incentivization weights

TODO: determine weight for shard attestations

| Name | Value |
| - | - |
| `TIMELY_SHARD_WEIGHT` | `uint64(8)` |

TODO: `WEIGHT_DENOMINATOR` needs to be adjusted, but this breaks a lot of Altair code.

## Preset

### Misc

| Name | Value | Notes |
| - | - | - |
| `MAX_SHARDS` | `uint64(2**10)` (= 1,024) | Theoretical max shard count (used to determine data structure sizes) |
| `INITIAL_ACTIVE_SHARDS` | `uint64(2**6)` (= 64) | Initial shard count |
| `SAMPLE_PRICE_ADJUSTMENT_COEFFICIENT` | `uint64(2**3)` (= 8) | Sample price may decrease/increase by at most exp(1 / this value) *per epoch* |
| `MAX_SHARD_PROPOSER_SLASHINGS` | `2**4` (= 16) | Maximum amount of shard proposer slashing operations per block |
| `MAX_SHARD_HEADERS_PER_SHARD` | `4` | |
| `SHARD_STATE_MEMORY_SLOTS` | `uint64(2**8)` (= 256) | Number of slots for which shard commitments and confirmation status is directly available in the state |
| `BLOB_BUILDER_REGISTRY_LIMIT` | `uint64(2**40)` (= 1,099,511,627,776) | shard blob builders |

### Shard blob samples

| Name | Value | Notes |
| - | - | - |
| `MAX_SAMPLES_PER_BLOB` | `uint64(2**11)` (= 2,048) | 248 * 2,048 = 507,904 bytes |
| `TARGET_SAMPLES_PER_BLOB` | `uint64(2**10)` (= 1,024) | 248 * 1,024 = 253,952 bytes |

### Precomputed size verification points

| Name | Value |
| - | - |
| `G1_SETUP` | Type `List[G1]`. The G1-side trusted setup `[G, G*s, G*s**2....]`; note that the first point is the generator. |
| `G2_SETUP` | Type `List[G2]`. The G2-side trusted setup `[G, G*s, G*s**2....]` |
| `ROOT_OF_UNITY` | `pow(PRIMITIVE_ROOT_OF_UNITY, (MODULUS - 1) // int(MAX_SAMPLES_PER_BLOB * POINTS_PER_SAMPLE), MODULUS)` |

### Gwei values

| Name | Value | Unit | Description |
| - | - | - | - |
| `MAX_SAMPLE_PRICE` | `Gwei(2**33)` (= 8,589,934,592) | Gwei | Max sample charged for a TARGET-sized shard blob |  
| `MIN_SAMPLE_PRICE` | `Gwei(2**3)` (= 8) | Gwei | Min sample price charged for a TARGET-sized shard blob |

## Configuration

Note: Some preset variables may become run-time configurable for testnets, but default to a preset while the spec is unstable.  
E.g. `INITIAL_ACTIVE_SHARDS`, `MAX_SAMPLES_PER_BLOB` and `TARGET_SAMPLES_PER_BLOB`.

## Updated containers

The following containers have updated definitions to support Sharding.

### `AttestationData`

```python
class AttestationData(Container):
    slot: Slot
    index: CommitteeIndex
    # LMD GHOST vote
    beacon_block_root: Root
    # FFG vote
    source: Checkpoint
    target: Checkpoint
    # Hash-tree-root of ShardBlob
    shard_blob_root: Root  # [New in Sharding]
```

### `BeaconBlockBody`

```python
class BeaconBlockBody(bellatrix.BeaconBlockBody):  # [extends Bellatrix block body]
    shard_proposer_slashings: List[ShardProposerSlashing, MAX_SHARD_PROPOSER_SLASHINGS]
    shard_headers: List[SignedShardBlobHeader, MAX_SHARDS * MAX_SHARD_HEADERS_PER_SHARD]
```

### `BeaconState`

```python
class BeaconState(bellatrix.BeaconState):
    # Blob builder registry.
    blob_builders: List[Builder, BLOB_BUILDER_REGISTRY_LIMIT]
    blob_builder_balances: List[Gwei, BLOB_BUILDER_REGISTRY_LIMIT]
    # A ring buffer of the latest slots, with information per active shard.
    shard_buffer: Vector[List[ShardWork, MAX_SHARDS], SHARD_STATE_MEMORY_SLOTS]
    shard_sample_price: uint64
```

## New containers

### `Builder`

```python
class Builder(Container):
    pubkey: BLSPubkey
    # TODO: fields for either an expiry mechanism (refunding execution account with remaining balance) 
    #  and/or a builder-transaction mechanism.
```

### `DataCommitment`

```python
class DataCommitment(Container):
    # KZG10 commitment to the data
    point: BLSCommitment
    # Length of the data in samples
    samples_count: uint64
```

### `AttestedDataCommitment`

```python
class AttestedDataCommitment(Container):
    # KZG10 commitment to the data, and length
    commitment: DataCommitment
    # hash_tree_root of the ShardBlobHeader (stored so that attestations can be checked against it)
    root: Root
    # The proposer who included the shard-header
    includer_index: ValidatorIndex
```

### `ShardBlobBody`

Unsigned shard data, bundled by a shard-builder.
Unique, signing different bodies as shard proposer for the same `(slot, shard)` is slashable.

```python
class ShardBlobBody(Container):
    # The actual data commitment
    commitment: DataCommitment
    # Proof that the degree < commitment.samples_count * POINTS_PER_SAMPLE
    degree_proof: BLSCommitment
    # The actual data. Should match the commitment and degree proof.
    data: List[BLSPoint, POINTS_PER_SAMPLE * MAX_SAMPLES_PER_BLOB]
    # fee payment fields (EIP 1559 like)
    # TODO: express in MWei instead?
    max_priority_fee_per_sample: Gwei
    max_fee_per_sample: Gwei
```

### `ShardBlobBodySummary`

Summary version of the `ShardBlobBody`, omitting the data payload, while preserving the data-commitments.

The commitments are not further collapsed to a single hash, 
to avoid an extra network roundtrip between proposer and builder, to include the header on-chain more quickly.

```python
class ShardBlobBodySummary(Container):
    # The actual data commitment
    commitment: DataCommitment
    # Proof that the degree < commitment.samples_count * POINTS_PER_SAMPLE
    degree_proof: BLSCommitment
    # Hash-tree-root as summary of the data field
    data_root: Root
    # fee payment fields (EIP 1559 like)
    # TODO: express in MWei instead?
    max_priority_fee_per_sample: Gwei
    max_fee_per_sample: Gwei
```

### `ShardBlob`

`ShardBlobBody` wrapped with the header data that is unique to the shard blob proposal.

```python
class ShardBlob(Container):
    slot: Slot
    shard: Shard
    # Builder of the data, pays data-fee to proposer
    builder_index: BuilderIndex
    # Proposer of the shard-blob
    proposer_index: ValidatorIndex
    # Blob contents
    body: ShardBlobBody
```

### `ShardBlobHeader`

Header version of `ShardBlob`.

```python
class ShardBlobHeader(Container):
    slot: Slot
    shard: Shard
    # Builder of the data, pays data-fee to proposer
    builder_index: BuilderIndex
    # Proposer of the shard-blob
    proposer_index: ValidatorIndex
    # Blob contents, without the full data
    body_summary: ShardBlobBodySummary
```

### `SignedShardBlob`

Full blob data, signed by the shard builder (ensuring fee payment) and shard proposer (ensuring a single proposal).

```python
class SignedShardBlob(Container):
    message: ShardBlob
    signature: BLSSignature
```

### `SignedShardBlobHeader`

Header of the blob, the signature is equally applicable to `SignedShardBlob`.
Shard proposers can accept `SignedShardBlobHeader` as a data-transaction by co-signing the header.

```python
class SignedShardBlobHeader(Container):
    message: ShardBlobHeader
    # Signature by builder.
    # Once accepted by proposer, the signatures is the aggregate of both.
    signature: BLSSignature
```

### `PendingShardHeader`

```python
class PendingShardHeader(Container):
    # The commitment that is attested
    attested: AttestedDataCommitment
    # Who voted for the header
    votes: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    # Sum of effective balances of votes
    weight: Gwei
    # When the header was last updated, as reference for weight accuracy
    update_slot: Slot
```

### `ShardBlobReference`

Reference version of `ShardBlobHeader`, substituting the body for just a hash-tree-root.

```python
class ShardBlobReference(Container):
    slot: Slot
    shard: Shard
    # Builder of the data
    builder_index: BuilderIndex
    # Proposer of the shard-blob
    proposer_index: ValidatorIndex
    # Blob hash-tree-root for slashing reference
    body_root: Root
```

### `ShardProposerSlashing`

```python
class ShardProposerSlashing(Container):
    slot: Slot
    shard: Shard
    proposer_index: ValidatorIndex
    builder_index_1: BuilderIndex
    builder_index_2: BuilderIndex
    body_root_1: Root
    body_root_2: Root
    signature_1: BLSSignature
    signature_2: BLSSignature
```

### `ShardWork`

```python
class ShardWork(Container):
    # Upon confirmation the data is reduced to just the commitment.
    status: Union[                                                   # See Shard Work Status enum
              None,                                                  # SHARD_WORK_UNCONFIRMED
              AttestedDataCommitment,                                # SHARD_WORK_CONFIRMED
              List[PendingShardHeader, MAX_SHARD_HEADERS_PER_SHARD]  # SHARD_WORK_PENDING
            ]
```

## Helper functions

### Misc

#### `next_power_of_two`

```python
def next_power_of_two(x: int) -> int:
    return 2 ** ((x - 1).bit_length())
```

#### `compute_previous_slot`

```python
def compute_previous_slot(slot: Slot) -> Slot:
    if slot > 0:
        return Slot(slot - 1)
    else:
        return Slot(0)
```

#### `compute_updated_sample_price`

```python
def compute_updated_sample_price(prev_price: Gwei, samples_length: uint64, active_shards: uint64) -> Gwei:
    adjustment_quotient = active_shards * SLOTS_PER_EPOCH * SAMPLE_PRICE_ADJUSTMENT_COEFFICIENT
    if samples_length > TARGET_SAMPLES_PER_BLOB:
        delta = max(1, prev_price * (samples_length - TARGET_SAMPLES_PER_BLOB) // TARGET_SAMPLES_PER_BLOB // adjustment_quotient)
        return min(prev_price + delta, MAX_SAMPLE_PRICE)
    else:
        delta = max(1, prev_price * (TARGET_SAMPLES_PER_BLOB - samples_length) // TARGET_SAMPLES_PER_BLOB // adjustment_quotient)
        return max(prev_price, MIN_SAMPLE_PRICE + delta) - delta
```

#### `compute_committee_source_epoch`

```python
def compute_committee_source_epoch(epoch: Epoch, period: uint64) -> Epoch:
    """
    Return the source epoch for computing the committee.
    """
    source_epoch = Epoch(epoch - epoch % period)
    if source_epoch >= period:
        source_epoch -= period  # `period` epochs lookahead
    return source_epoch
```

#### `batch_apply_participation_flag`

```python
def batch_apply_participation_flag(state: BeaconState, bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE],
                                   epoch: Epoch, full_committee: Sequence[ValidatorIndex], flag_index: int):
    if epoch == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation
    for bit, index in zip(bits, full_committee):
        if bit:
            epoch_participation[index] = add_flag(epoch_participation[index], flag_index)
```

### Beacon state accessors

#### Updated `get_committee_count_per_slot`

```python
def get_committee_count_per_slot(state: BeaconState, epoch: Epoch) -> uint64:
    """
    Return the number of committees in each slot for the given ``epoch``.
    """
    return max(uint64(1), min(
        get_active_shard_count(state, epoch),
        uint64(len(get_active_validator_indices(state, epoch))) // SLOTS_PER_EPOCH // TARGET_COMMITTEE_SIZE,
    ))
```

#### `get_active_shard_count`

```python
def get_active_shard_count(state: BeaconState, epoch: Epoch) -> uint64:
    """
    Return the number of active shards.
    Note that this puts an upper bound on the number of committees per slot.
    """
    return INITIAL_ACTIVE_SHARDS
```

#### `get_shard_proposer_index`

```python
def get_shard_proposer_index(state: BeaconState, slot: Slot, shard: Shard) -> ValidatorIndex:
    """
    Return the proposer's index of shard block at ``slot``.
    """
    epoch = compute_epoch_at_slot(slot)
    seed = hash(get_seed(state, epoch, DOMAIN_SHARD_BLOB) + uint_to_bytes(slot) + uint_to_bytes(shard))
    indices = get_active_validator_indices(state, epoch)
    return compute_proposer_index(state, indices, seed)
```

#### `get_start_shard`

```python
def get_start_shard(state: BeaconState, slot: Slot) -> Shard:
    """
    Return the start shard at ``slot``.
    """
    epoch = compute_epoch_at_slot(Slot(slot))
    committee_count = get_committee_count_per_slot(state, epoch)
    active_shard_count = get_active_shard_count(state, epoch)
    return committee_count * slot % active_shard_count 
```

#### `compute_shard_from_committee_index`

```python
def compute_shard_from_committee_index(state: BeaconState, slot: Slot, index: CommitteeIndex) -> Shard:
    active_shards = get_active_shard_count(state, compute_epoch_at_slot(slot))
    assert index < active_shards
    return Shard((index + get_start_shard(state, slot)) % active_shards)
```

#### `compute_committee_index_from_shard`

```python
def compute_committee_index_from_shard(state: BeaconState, slot: Slot, shard: Shard) -> CommitteeIndex:
    epoch = compute_epoch_at_slot(slot)
    active_shards = get_active_shard_count(state, epoch)
    index = CommitteeIndex((active_shards + shard - get_start_shard(state, slot)) % active_shards)
    assert index < get_committee_count_per_slot(state, epoch)
    return index
```


### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    # is_execution_enabled is omitted, execution is enabled by default.
    process_execution_payload(state, block.body.execution_payload, EXECUTION_ENGINE)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)  # [Modified in Sharding]
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### Operations

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

    # TODO: to avoid parallel shards racing, and avoid inclusion-order problems,
    #  update the fee price per slot, instead of per header.
    # state.shard_sample_price = compute_updated_sample_price(state.shard_sample_price, ?, shard_count)
```

##### Extended Attestation processing

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    altair.process_attestation(state, attestation)
    process_attested_shard_work(state, attestation)
```

```python
def process_attested_shard_work(state: BeaconState, attestation: Attestation) -> None:
    attestation_shard = compute_shard_from_committee_index(
        state,
        attestation.data.slot,
        attestation.data.index,
    )
    full_committee = get_beacon_committee(state, attestation.data.slot, attestation.data.index)

    buffer_index = attestation.data.slot % SHARD_STATE_MEMORY_SLOTS
    committee_work = state.shard_buffer[buffer_index][attestation_shard]

    # Skip attestation vote accounting if the header is not pending
    if committee_work.status.selector != SHARD_WORK_PENDING:
        # If the data was already confirmed, check if this matches, to apply the flag to the attesters.
        if committee_work.status.selector == SHARD_WORK_CONFIRMED:
            attested: AttestedDataCommitment = committee_work.status.value
            if attested.root == attestation.data.shard_blob_root:
                batch_apply_participation_flag(state, attestation.aggregation_bits,
                                               attestation.data.target.epoch,
                                               full_committee, TIMELY_SHARD_FLAG_INDEX)
        return

    current_headers: Sequence[PendingShardHeader] = committee_work.status.value

    # Find the corresponding header, abort if it cannot be found
    header_index = len(current_headers)
    for i, header in enumerate(current_headers):
        if attestation.data.shard_blob_root == header.attested.root:
            header_index = i
            break

    # Attestations for an unknown header do not count towards shard confirmations, but can otherwise be valid.
    if header_index == len(current_headers):
        # Note: Attestations may be re-included if headers are included late.
        return

    pending_header: PendingShardHeader = current_headers[header_index]

    # The weight may be outdated if it is not the initial weight, and from a previous epoch
    if pending_header.weight != 0 and compute_epoch_at_slot(pending_header.update_slot) < get_current_epoch(state):
        pending_header.weight = sum(state.validators[index].effective_balance for index, bit
                                    in zip(full_committee, pending_header.votes) if bit)

    pending_header.update_slot = state.slot

    full_committee_balance = Gwei(0)
    # Update votes bitfield in the state, update weights
    for i, bit in enumerate(attestation.aggregation_bits):
        weight = state.validators[full_committee[i]].effective_balance
        full_committee_balance += weight
        if bit:
            if not pending_header.votes[i]:
                pending_header.weight += weight
                pending_header.votes[i] = True

    # Check if the PendingShardHeader is eligible for expedited confirmation, requiring 2/3 of balance attesting
    if pending_header.weight * 3 >= full_committee_balance * 2:
        # participants of the winning header are remembered with participation flags
        batch_apply_participation_flag(state, pending_header.votes, attestation.data.target.epoch,
                                       full_committee, TIMELY_SHARD_FLAG_INDEX)

        if pending_header.attested.commitment == DataCommitment():
            # The committee voted to not confirm anything
            state.shard_buffer[buffer_index][attestation_shard].status.change(
                selector=SHARD_WORK_UNCONFIRMED,
                value=None,
            )
        else:
            state.shard_buffer[buffer_index][attestation_shard].status.change(
                selector=SHARD_WORK_CONFIRMED,
                value=pending_header.attested,
            )
```

##### `process_shard_header`

```python
def process_shard_header(state: BeaconState, signed_header: SignedShardBlobHeader) -> None:
    header: ShardBlobHeader = signed_header.message
    slot = header.slot
    shard = header.shard

    # Verify the header is not 0, and not from the future.
    assert Slot(0) < slot <= state.slot
    header_epoch = compute_epoch_at_slot(slot)
    # Verify that the header is within the processing time window
    assert header_epoch in [get_previous_epoch(state), get_current_epoch(state)]
    # Verify that the shard is valid
    shard_count = get_active_shard_count(state, header_epoch)
    assert shard < shard_count
    # Verify that a committee is able to attest this (slot, shard)
    start_shard = get_start_shard(state, slot)
    committee_index = (shard_count + shard - start_shard) % shard_count    
    committees_per_slot = get_committee_count_per_slot(state, header_epoch)
    assert committee_index <= committees_per_slot

    # Check that this data is still pending
    committee_work = state.shard_buffer[slot % SHARD_STATE_MEMORY_SLOTS][shard]
    assert committee_work.status.selector == SHARD_WORK_PENDING

    # Check that this header is not yet in the pending list
    current_headers: List[PendingShardHeader, MAX_SHARD_HEADERS_PER_SHARD] = committee_work.status.value
    header_root = hash_tree_root(header)
    assert header_root not in [pending_header.attested.root for pending_header in current_headers]

    # Verify proposer matches
    assert header.proposer_index == get_shard_proposer_index(state, slot, shard)

    # Verify builder and proposer aggregate signature
    blob_signing_root = compute_signing_root(header, get_domain(state, DOMAIN_SHARD_BLOB))
    builder_pubkey = state.blob_builders[header.builder_index].pubkey
    proposer_pubkey = state.validators[header.proposer_index].pubkey
    assert bls.FastAggregateVerify([builder_pubkey, proposer_pubkey], blob_signing_root, signed_header.signature)

    # Verify the length by verifying the degree.
    body_summary = header.body_summary
    points_count = body_summary.commitment.samples_count * POINTS_PER_SAMPLE
    if points_count == 0:
        assert body_summary.degree_proof == G1_SETUP[0]
    assert (
        bls.Pairing(body_summary.degree_proof, G2_SETUP[0])
        == bls.Pairing(body_summary.commitment.point, G2_SETUP[-points_count])
    )

    # Charge EIP 1559 fee, builder pays for opportunity, and is responsible for later availability,
    # or fail to publish at their own expense.
    samples = body_summary.commitment.samples_count
    # TODO: overflows, need bigger int type
    max_fee = body_summary.max_fee_per_sample * samples

    # Builder must have sufficient balance, even if max_fee is not completely utilized
    assert state.blob_builder_balances[header.builder_index] >= max_fee

    base_fee = state.shard_sample_price * samples
    # Base fee must be paid
    assert max_fee >= base_fee

    # Remaining fee goes towards proposer for prioritizing, up to a maximum
    max_priority_fee = body_summary.max_priority_fee_per_sample * samples
    priority_fee = min(max_fee - base_fee, max_priority_fee)

    # Burn base fee, take priority fee
    # priority_fee <= max_fee - base_fee, thus priority_fee + base_fee <= max_fee, thus sufficient balance.
    state.blob_builder_balances[header.builder_index] -= base_fee + priority_fee
    # Pay out priority fee
    increase_balance(state, header.proposer_index, priority_fee)

    # Initialize the pending header
    index = compute_committee_index_from_shard(state, slot, shard)
    committee_length = len(get_beacon_committee(state, slot, index))
    initial_votes = Bitlist[MAX_VALIDATORS_PER_COMMITTEE]([0] * committee_length)
    pending_header = PendingShardHeader(
        attested=AttestedDataCommitment(
            commitment=body_summary.commitment,
            root=header_root,
            includer_index=get_beacon_proposer_index(state),
        ),
        votes=initial_votes,
        weight=0,
        update_slot=state.slot,
    )

    # Include it in the pending list
    current_headers.append(pending_header)
```

The degree proof works as follows. For a block `B` with length `l` (so `l`  values in `[0...l - 1]`, seen as a polynomial `B(X)` which takes these values),
the length proof is the commitment to the polynomial `B(X) * X**(MAX_DEGREE + 1 - l)`,
where `MAX_DEGREE` is the maximum power of `s` available in the setup, which is `MAX_DEGREE = len(G2_SETUP) - 1`.
The goal is to ensure that a proof can only be constructed if `deg(B) < l` (there are not hidden higher-order terms in the polynomial, which would thwart reconstruction).

##### `process_shard_proposer_slashing`

```python
def process_shard_proposer_slashing(state: BeaconState, proposer_slashing: ShardProposerSlashing) -> None:
    slot = proposer_slashing.slot
    shard = proposer_slashing.shard
    proposer_index = proposer_slashing.proposer_index

    reference_1 = ShardBlobReference(slot=slot, shard=shard,
                                     proposer_index=proposer_index,
                                     builder_index=proposer_slashing.builder_index_1,
                                     body_root=proposer_slashing.body_root_1)
    reference_2 = ShardBlobReference(slot=slot, shard=shard,
                                     proposer_index=proposer_index,
                                     builder_index=proposer_slashing.builder_index_2,
                                     body_root=proposer_slashing.body_root_2)

    # Verify the signed messages are different
    assert reference_1 != reference_2

    # Verify the proposer is slashable
    proposer = state.validators[proposer_index]
    assert is_slashable_validator(proposer, get_current_epoch(state))

    # The builders are not slashed, the proposer co-signed with them
    builder_pubkey_1 = state.blob_builders[proposer_slashing.builder_index_1].pubkey
    builder_pubkey_2 = state.blob_builders[proposer_slashing.builder_index_2].pubkey
    domain = get_domain(state, DOMAIN_SHARD_PROPOSER, compute_epoch_at_slot(slot))
    signing_root_1 = compute_signing_root(reference_1, domain)
    signing_root_2 = compute_signing_root(reference_2, domain)
    assert bls.FastAggregateVerify([builder_pubkey_1, proposer.pubkey], signing_root_1, proposer_slashing.signature_1)
    assert bls.FastAggregateVerify([builder_pubkey_2, proposer.pubkey], signing_root_2, proposer_slashing.signature_2)

    slash_validator(state, proposer_index)
```

### Epoch transition

This epoch transition overrides Bellatrix epoch transition:

```python
def process_epoch(state: BeaconState) -> None:
    # Sharding pre-processing
    process_pending_shard_confirmations(state)
    reset_pending_shard_work(state)

    # Base functionality
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)  # Note: modified, see new TIMELY_SHARD_FLAG_INDEX
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

#### `process_pending_shard_confirmations`

```python
def process_pending_shard_confirmations(state: BeaconState) -> None:
    # Pending header processing applies to the previous epoch.
    # Skip if `GENESIS_EPOCH` because no prior epoch to process.
    if get_current_epoch(state) == GENESIS_EPOCH:
        return

    previous_epoch = get_previous_epoch(state)
    previous_epoch_start_slot = compute_start_slot_at_epoch(previous_epoch)

    # Mark stale headers as unconfirmed
    for slot in range(previous_epoch_start_slot, previous_epoch_start_slot + SLOTS_PER_EPOCH):
        buffer_index = slot % SHARD_STATE_MEMORY_SLOTS
        for shard_index in range(len(state.shard_buffer[buffer_index])):
            committee_work = state.shard_buffer[buffer_index][shard_index]
            if committee_work.status.selector == SHARD_WORK_PENDING:
                winning_header = max(committee_work.status.value, key=lambda header: header.weight)
                if winning_header.attested.commitment == DataCommitment():
                    committee_work.status.change(selector=SHARD_WORK_UNCONFIRMED, value=None)
                else:
                    committee_work.status.change(selector=SHARD_WORK_CONFIRMED, value=winning_header.attested)
```

#### `reset_pending_shard_work`

```python
def reset_pending_shard_work(state: BeaconState) -> None:
    # Add dummy "empty" PendingShardHeader (default vote if no shard header is available)
    next_epoch = get_current_epoch(state) + 1
    next_epoch_start_slot = compute_start_slot_at_epoch(next_epoch)
    committees_per_slot = get_committee_count_per_slot(state, next_epoch)
    active_shards = get_active_shard_count(state, next_epoch)

    for slot in range(next_epoch_start_slot, next_epoch_start_slot + SLOTS_PER_EPOCH):
        buffer_index = slot % SHARD_STATE_MEMORY_SLOTS
        
        # Reset the shard work tracking
        state.shard_buffer[buffer_index] = [ShardWork() for _ in range(active_shards)]

        start_shard = get_start_shard(state, slot)
        for committee_index in range(committees_per_slot):
            shard = (start_shard + committee_index) % active_shards
            # a committee is available, initialize a pending shard-header list
            committee_length = len(get_beacon_committee(state, slot, CommitteeIndex(committee_index)))
            state.shard_buffer[buffer_index][shard].status.change(
                selector=SHARD_WORK_PENDING,
                value=List[PendingShardHeader, MAX_SHARD_HEADERS_PER_SHARD](
                    PendingShardHeader(
                        attested=AttestedDataCommitment(),
                        votes=Bitlist[MAX_VALIDATORS_PER_COMMITTEE]([0] * committee_length),
                        weight=0,
                        update_slot=slot,
                    )
                )
            )
        # a shard without committee available defaults to SHARD_WORK_UNCONFIRMED.
```
