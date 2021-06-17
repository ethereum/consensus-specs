# Ethereum 2.0 Sharding -- Beacon Chain changes 

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
  - [Misc](#misc)
  - [Domain types](#domain-types)
  - [Shard Work Status](#shard-work-status)
- [Preset](#preset)
  - [Misc](#misc-1)
  - [Shard block samples](#shard-block-samples)
  - [Precomputed size verification points](#precomputed-size-verification-points)
  - [Gwei values](#gwei-values)
- [Configuration](#configuration)
- [Updated containers](#updated-containers)
  - [`AttestationData`](#attestationdata)
  - [`BeaconBlockBody`](#beaconblockbody)
  - [`BeaconState`](#beaconstate)
- [New containers](#new-containers)
  - [`DataCommitment`](#datacommitment)
  - [`ShardBlobBodySummary`](#shardblobbodysummary)
  - [`ShardBlobHeader`](#shardblobheader)
  - [`SignedShardBlobHeader`](#signedshardblobheader)
  - [`PendingShardHeader`](#pendingshardheader)
  - [`ShardBlobReference`](#shardblobreference)
  - [`SignedShardBlobReference`](#signedshardblobreference)
  - [`ShardProposerSlashing`](#shardproposerslashing)
  - [`ShardWork`](#shardwork)
- [Helper functions](#helper-functions)
  - [Misc](#misc-2)
    - [`next_power_of_two`](#next_power_of_two)
    - [`compute_previous_slot`](#compute_previous_slot)
    - [`compute_updated_gasprice`](#compute_updated_gasprice)
    - [`compute_committee_source_epoch`](#compute_committee_source_epoch)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Updated `get_committee_count_per_slot`](#updated-get_committee_count_per_slot)
    - [`get_active_shard_count`](#get_active_shard_count)
    - [`get_shard_committee`](#get_shard_committee)
    - [`compute_proposer_index`](#compute_proposer_index)
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
    - [`charge_confirmed_shard_fees`](#charge_confirmed_shard_fees)
    - [`reset_pending_shard_work`](#reset_pending_shard_work)
    - [`process_shard_epoch_increment`](#process_shard_epoch_increment)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->


## Introduction

This document describes the extensions made to the Phase 0 design of The Beacon Chain to support data sharding,
based on the ideas [here](https://hackmd.io/G-Iy5jqyT7CXWEz8Ssos8g) and more broadly [here](https://arxiv.org/abs/1809.09044),
using KZG10 commitments to commit to data to remove any need for fraud proofs (and hence, safety-critical synchrony assumptions) in the design.


## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `Shard` | `uint64` | A shard number |
| `BLSCommitment` | `Bytes48` | A G1 curve point |
| `BLSPoint` | `uint256` | A number `x` in the range `0 <= x < MODULUS` |

## Constants

The following values are (non-configurable) constants used throughout the specification.

### Misc

| Name | Value | Notes |
| - | - | - |
| `PRIMITIVE_ROOT_OF_UNITY` | `5` | Primitive root of unity of the BLS12_381 (inner) modulus |
| `DATA_AVAILABILITY_INVERSE_CODING_RATE` | `2**1` (= 2) | Factor by which samples are extended for data availability encoding |
| `POINTS_PER_SAMPLE` | `uint64(2**3)` (= 8) | 31 * 8 = 248 bytes |
| `MODULUS` | `0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001` (curve order of BLS12_381) |

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_SHARD_PROPOSER` | `DomainType('0x80000000')` |
| `DOMAIN_SHARD_COMMITTEE` | `DomainType('0x81000000')` |

### Shard Work Status

| Name | Value | Notes |
| - | - | - |
| `SHARD_WORK_UNCONFIRMED` | `0` | Unconfirmed, nullified after confirmation time elapses |
| `SHARD_WORK_CONFIRMED` | `1` | Confirmed, reduced to just the commitment |
| `SHARD_WORK_PENDING` | `2` | Pending, a list of competing headers |

## Preset

### Misc

| Name | Value | Notes |
| - | - | - |
| `MAX_SHARDS` | `uint64(2**10)` (= 1,024) | Theoretical max shard count (used to determine data structure sizes) |
| `GASPRICE_ADJUSTMENT_COEFFICIENT` | `uint64(2**3)` (= 8) | Gasprice may decrease/increase by at most exp(1 / this value) *per epoch* |
| `MAX_SHARD_PROPOSER_SLASHINGS` | `2**4` (= 16) | Maximum amount of shard proposer slashing operations per block |
| `MAX_SHARD_HEADERS_PER_SHARD` | `4` | |
| `SHARD_STATE_MEMORY_SLOTS` | `uint64(2**8)` (= 256) | Number of slots for which shard commitments and confirmation status is directly available in the state |

### Shard block samples

| Name | Value | Notes |
| - | - | - |
| `MAX_SAMPLES_PER_BLOCK` | `uint64(2**11)` (= 2,048) | 248 * 2,048 = 507,904 bytes |
| `TARGET_SAMPLES_PER_BLOCK` | `uint64(2**10)` (= 1,024) | 248 * 1,024 = 253,952 bytes |

### Precomputed size verification points

| Name | Value |
| - | - |
| `G1_SETUP` | Type `List[G1]`. The G1-side trusted setup `[G, G*s, G*s**2....]`; note that the first point is the generator. |
| `G2_SETUP` | Type `List[G2]`. The G2-side trusted setup `[G, G*s, G*s**2....]` |
| `ROOT_OF_UNITY` | `pow(PRIMITIVE_ROOT_OF_UNITY, (MODULUS - 1) // int(MAX_SAMPLES_PER_BLOCK * POINTS_PER_SAMPLE), MODULUS)` |

### Gwei values

| Name | Value | Unit | Description |
| - | - | - | - |
| `MAX_GASPRICE` | `Gwei(2**33)` (= 8,589,934,592) | Gwei | Max gasprice charged for a TARGET-sized shard block |  
| `MIN_GASPRICE` | `Gwei(2**3)` (= 8) | Gwei | Min gasprice charged for a TARGET-sized shard block |

## Configuration

| Name | Value | Notes |
| - | - | - |
| `INITIAL_ACTIVE_SHARDS` | `uint64(2**6)` (= 64) | Initial shard count |

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
    # Shard header root
    shard_header_root: Root  # [New in Sharding]
```

### `BeaconBlockBody`

```python
class BeaconBlockBody(merge.BeaconBlockBody):  # [extends The Merge block body]
    shard_proposer_slashings: List[ShardProposerSlashing, MAX_SHARD_PROPOSER_SLASHINGS]
    shard_headers: List[SignedShardBlobHeader, MAX_SHARDS * MAX_SHARD_HEADERS_PER_SHARD]
```

### `BeaconState`

```python
class BeaconState(merge.BeaconState):  # [extends The Merge state]
    # [Updated fields] (Warning: this changes with Altair, Sharding will rebase to use participation-flags)
    previous_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    current_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    # [New fields]
    # A ring buffer of the latest slots, with information per active shard.
    shard_buffer: Vector[List[ShardWork, MAX_SHARDS], SHARD_STATE_MEMORY_SLOTS]
    shard_gasprice: uint64
    current_epoch_start_shard: Shard
```

## New containers

The shard data itself is network-layer only, and can be found in the [P2P specification](./p2p-interface.md).
The beacon chain registers just the commitments of the shard data.

### `DataCommitment`

```python
class DataCommitment(Container):
    # KZG10 commitment to the data
    point: BLSCommitment
    # Length of the data in samples
    length: uint64
```

### `ShardBlobBodySummary`

```python
class ShardBlobBodySummary(Container):
    # The actual data commitment
    commitment: DataCommitment
    # Proof that the degree < commitment.length
    degree_proof: BLSCommitment
    # Hash-tree-root as summary of the data field
    data_root: Root
    # Latest block root of the Beacon Chain, before shard_blob.slot
    beacon_block_root: Root
```

### `ShardBlobHeader`

```python
class ShardBlobHeader(Container):
    # Slot and shard that this header is intended for
    slot: Slot
    shard: Shard
    # SSZ-summary of ShardBlobBody
    body_summary: ShardBlobBodySummary
    # Proposer of the shard-blob
    proposer_index: ValidatorIndex
```

### `SignedShardBlobHeader`

```python
class SignedShardBlobHeader(Container):
    message: ShardBlobHeader
    signature: BLSSignature
```

### `PendingShardHeader`

```python
class PendingShardHeader(Container):
    # KZG10 commitment to the data
    commitment: DataCommitment
    # hash_tree_root of the ShardHeader (stored so that attestations can be checked against it)
    root: Root
    # Who voted for the header
    votes: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    # Sum of effective balances of votes
    weight: Gwei
    # When the header was last updated, as reference for weight accuracy
    update_slot: Slot
```

### `ShardBlobReference`

```python
class ShardBlobReference(Container):
    # Slot and shard that this reference is intended for
    slot: Slot
    shard: Shard
    # Hash-tree-root of ShardBlobBody
    body_root: Root
    # Proposer of the shard-blob
    proposer_index: ValidatorIndex
```

### `SignedShardBlobReference`

```python
class SignedShardBlobReference(Container):
    message: ShardBlobReference
    signature: BLSSignature
```

### `ShardProposerSlashing`

```python
class ShardProposerSlashing(Container):
    signed_reference_1: SignedShardBlobReference
    signed_reference_2: SignedShardBlobReference
```

### `ShardWork`

```python
class ShardWork(Container):
    #  Upon confirmation the data is reduced to just the header.
    status: Union[                                                   # See Shard Work Status enum
              None,                                                  # SHARD_WORK_UNCONFIRMED
              DataCommitment,                                        # SHARD_WORK_CONFIRMED
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

#### `compute_updated_gasprice`

```python
def compute_updated_gasprice(prev_gasprice: Gwei, shard_block_length: uint64, adjustment_quotient: uint64) -> Gwei:
    if shard_block_length > TARGET_SAMPLES_PER_BLOCK:
        delta = max(1, prev_gasprice * (shard_block_length - TARGET_SAMPLES_PER_BLOCK)
                       // TARGET_SAMPLES_PER_BLOCK // adjustment_quotient)
        return min(prev_gasprice + delta, MAX_GASPRICE)
    else:
        delta = max(1, prev_gasprice * (TARGET_SAMPLES_PER_BLOCK - shard_block_length)
                       // TARGET_SAMPLES_PER_BLOCK // adjustment_quotient)
        return max(prev_gasprice, MIN_GASPRICE + delta) - delta
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

#### `get_shard_committee`

```python
def get_shard_committee(beacon_state: BeaconState, epoch: Epoch, shard: Shard) -> Sequence[ValidatorIndex]:
    """
    Return the shard committee of the given ``epoch`` of the given ``shard``.
    """
    source_epoch = compute_committee_source_epoch(epoch, SHARD_COMMITTEE_PERIOD)
    active_validator_indices = get_active_validator_indices(beacon_state, source_epoch)
    seed = get_seed(beacon_state, source_epoch, DOMAIN_SHARD_COMMITTEE)
    return compute_committee(
        indices=active_validator_indices,
        seed=seed,
        index=shard,
        count=get_active_shard_count(beacon_state, epoch),
    )
```

#### `compute_proposer_index`

Updated version to get a proposer index that will only allow proposers with a certain minimum balance,
ensuring that the balance is always sufficient to cover gas costs.

```python
def compute_proposer_index(beacon_state: BeaconState,
                           indices: Sequence[ValidatorIndex],
                           seed: Bytes32,
                           min_effective_balance: Gwei = Gwei(0)) -> ValidatorIndex:
    """
    Return from ``indices`` a random index sampled by effective balance.
    """
    assert len(indices) > 0
    MAX_RANDOM_BYTE = 2**8 - 1
    i = uint64(0)
    total = uint64(len(indices))
    while True:
        candidate_index = indices[compute_shuffled_index(i % total, total, seed)]
        random_byte = hash(seed + uint_to_bytes(uint64(i // 32)))[i % 32]
        effective_balance = beacon_state.validators[candidate_index].effective_balance
        if effective_balance <= min_effective_balance:
            continue
        if effective_balance * MAX_RANDOM_BYTE >= MAX_EFFECTIVE_BALANCE * random_byte:
            return candidate_index
        i += 1
```

#### `get_shard_proposer_index`

```python
def get_shard_proposer_index(beacon_state: BeaconState, slot: Slot, shard: Shard) -> ValidatorIndex:
    """
    Return the proposer's index of shard block at ``slot``.
    """
    epoch = compute_epoch_at_slot(slot)
    committee = get_shard_committee(beacon_state, epoch, shard)
    seed = hash(get_seed(beacon_state, epoch, DOMAIN_SHARD_PROPOSER) + uint_to_bytes(slot))

    # Proposer must have sufficient balance to pay for worst case fee burn
    EFFECTIVE_BALANCE_MAX_DOWNWARD_DEVIATION = (
        EFFECTIVE_BALANCE_INCREMENT - EFFECTIVE_BALANCE_INCREMENT
        * HYSTERESIS_DOWNWARD_MULTIPLIER // HYSTERESIS_QUOTIENT
    )
    min_effective_balance = (
        beacon_state.shard_gasprice * MAX_SAMPLES_PER_BLOCK // TARGET_SAMPLES_PER_BLOCK
        + EFFECTIVE_BALANCE_MAX_DOWNWARD_DEVIATION
    )
    return compute_proposer_index(beacon_state, committee, seed, min_effective_balance)
```

#### `get_start_shard`

```python
def get_start_shard(state: BeaconState, slot: Slot) -> Shard:
    """
    Return the start shard at ``slot``.
    """
    current_epoch_start_slot = compute_start_slot_at_epoch(get_current_epoch(state))
    shard = state.current_epoch_start_shard
    if slot > current_epoch_start_slot:
        # Current epoch or the next epoch lookahead
        for _slot in range(current_epoch_start_slot, slot):
            committee_count = get_committee_count_per_slot(state, compute_epoch_at_slot(Slot(_slot)))
            active_shard_count = get_active_shard_count(state, compute_epoch_at_slot(Slot(_slot)))
            shard = (shard + committee_count) % active_shard_count
    elif slot < current_epoch_start_slot:
        # Previous epoch
        for _slot in list(range(slot, current_epoch_start_slot))[::-1]:
            committee_count = get_committee_count_per_slot(state, compute_epoch_at_slot(Slot(_slot)))
            active_shard_count = get_active_shard_count(state, compute_epoch_at_slot(Slot(_slot)))
            # Ensure positive
            shard = (shard + active_shard_count - committee_count) % active_shard_count
    return Shard(shard)
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
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)  # [Modified in Sharding]
    # Pre-merge, skip execution payload processing
    if is_execution_enabled(state, block):
        process_execution_payload(state, block.body.execution_payload, EXECUTION_ENGINE)  # [New in Merge]
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
    # Limit is dynamic based on active shard count
    assert len(body.shard_headers) <= MAX_SHARD_HEADERS_PER_SHARD * get_active_shard_count(state, get_current_epoch(state))
    for_ops(body.shard_headers, process_shard_header)
    # New attestation processing
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)
```

##### Extended Attestation processing

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    phase0.process_attestation(state, attestation)
    update_pending_shard_work(state, attestation)
```

```python
def update_pending_shard_work(state: BeaconState, attestation: Attestation) -> None:
    attestation_shard = compute_shard_from_committee_index(
        state,
        attestation.data.slot,
        attestation.data.index,
    )
    buffer_index = attestation.data.slot % SHARD_STATE_MEMORY_SLOTS
    committee_work = state.shard_buffer[buffer_index][attestation_shard]

    # Skip attestation vote accounting if the header is not pending
    if committee_work.status.selector != SHARD_WORK_PENDING:
        # TODO In Altair: set participation bit flag, if attestation matches winning header.
        return

    current_headers: Sequence[PendingShardHeader] = committee_work.status.value

    # Find the corresponding header, abort if it cannot be found
    header_index = [header.root for header in current_headers].index(attestation.data.shard_header_root)

    pending_header: PendingShardHeader = current_headers[header_index]
    full_committee = get_beacon_committee(state, attestation.data.slot, attestation.data.index)

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
        # TODO In Altair: set participation bit flag for voters of this early winning header
        if pending_header.commitment == DataCommitment():
            # The committee voted to not confirm anything
            state.shard_buffer[buffer_index][attestation_shard].status.change(
                selector=SHARD_WORK_UNCONFIRMED,
                value=None,
            )
        else:
            state.shard_buffer[buffer_index][attestation_shard].status.change(
                selector=SHARD_WORK_CONFIRMED,
                value=pending_header.commitment,
            )
```

##### `process_shard_header`

```python
def process_shard_header(state: BeaconState, signed_header: SignedShardBlobHeader) -> None:
    header = signed_header.message
    # Verify the header is not 0, and not from the future.
    assert Slot(0) < header.slot <= state.slot
    header_epoch = compute_epoch_at_slot(header.slot)
    # Verify that the header is within the processing time window
    assert header_epoch in [get_previous_epoch(state), get_current_epoch(state)]
    # Verify that the shard is active
    assert header.shard < get_active_shard_count(state, header_epoch)
    # Verify that the block root matches,
    # to ensure the header will only be included in this specific Beacon Chain sub-tree.
    assert header.body_summary.beacon_block_root == get_block_root_at_slot(state, header.slot - 1)

    # Check that this data is still pending
    committee_work = state.shard_buffer[header.slot % SHARD_STATE_MEMORY_SLOTS][header.shard]
    assert committee_work.status.selector == SHARD_WORK_PENDING

    # Check that this header is not yet in the pending list
    current_headers: List[PendingShardHeader, MAX_SHARD_HEADERS_PER_SHARD] = committee_work.status.value
    header_root = hash_tree_root(header)
    assert header_root not in [pending_header.root for pending_header in current_headers]

    # Verify proposer
    assert header.proposer_index == get_shard_proposer_index(state, header.slot, header.shard)
    # Verify signature
    signing_root = compute_signing_root(header, get_domain(state, DOMAIN_SHARD_PROPOSER))
    assert bls.Verify(state.validators[header.proposer_index].pubkey, signing_root, signed_header.signature)

    # Verify the length by verifying the degree.
    body_summary = header.body_summary
    if body_summary.commitment.length == 0:
        assert body_summary.degree_proof == G1_SETUP[0]
    assert (
        bls.Pairing(body_summary.degree_proof, G2_SETUP[0])
        == bls.Pairing(body_summary.commitment.point, G2_SETUP[-body_summary.commitment.length])
    )

    # Initialize the pending header
    index = compute_committee_index_from_shard(state, header.slot, header.shard)
    committee_length = len(get_beacon_committee(state, header.slot, index))
    initial_votes = Bitlist[MAX_VALIDATORS_PER_COMMITTEE]([0] * committee_length)
    pending_header = PendingShardHeader(
        commitment=body_summary.commitment,
        root=header_root,
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
    reference_1 = proposer_slashing.signed_reference_1.message
    reference_2 = proposer_slashing.signed_reference_2.message

    # Verify header slots match
    assert reference_1.slot == reference_2.slot
    # Verify header shards match
    assert reference_1.shard == reference_2.shard
    # Verify header proposer indices match
    assert reference_1.proposer_index == reference_2.proposer_index
    # Verify the headers are different (i.e. different body)
    assert reference_1 != reference_2
    # Verify the proposer is slashable
    proposer = state.validators[reference_1.proposer_index]
    assert is_slashable_validator(proposer, get_current_epoch(state))
    # Verify signatures
    for signed_header in (proposer_slashing.signed_reference_1, proposer_slashing.signed_reference_2):
        domain = get_domain(state, DOMAIN_SHARD_PROPOSER, compute_epoch_at_slot(signed_header.message.slot))
        signing_root = compute_signing_root(signed_header.message, domain)
        assert bls.Verify(proposer.pubkey, signing_root, signed_header.signature)

    slash_validator(state, reference_1.proposer_index)
```

### Epoch transition

This epoch transition overrides the Merge epoch transition:

```python
def process_epoch(state: BeaconState) -> None:
    # Sharding
    process_pending_shard_confirmations(state)
    charge_confirmed_shard_fees(state)
    reset_pending_shard_work(state)

    # Phase0
    process_justification_and_finalization(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)

    # Final updates
    process_eth1_data_reset(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_roots_update(state)
    process_participation_record_updates(state)

    process_shard_epoch_increment(state)
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
                # TODO In Altair: set participation bit flag of voters for winning header
                if winning_header.commitment == DataCommitment():
                    committee_work.status.change(selector=SHARD_WORK_UNCONFIRMED, value=None)
                else:
                    committee_work.status.change(selector=SHARD_WORK_CONFIRMED, value=winning_header.commitment)
```

#### `charge_confirmed_shard_fees`

```python
def charge_confirmed_shard_fees(state: BeaconState) -> None:
    new_gasprice = state.shard_gasprice
    previous_epoch = get_previous_epoch(state)
    previous_epoch_start_slot = compute_start_slot_at_epoch(previous_epoch)
    adjustment_quotient = (
        get_active_shard_count(state, previous_epoch)
        * SLOTS_PER_EPOCH * GASPRICE_ADJUSTMENT_COEFFICIENT
    )
    # Iterate through confirmed shard-headers
    for slot in range(previous_epoch_start_slot, previous_epoch_start_slot + SLOTS_PER_EPOCH):
        buffer_index = slot % SHARD_STATE_MEMORY_SLOTS
        for shard_index in range(len(state.shard_buffer[buffer_index])):
            committee_work = state.shard_buffer[buffer_index][shard_index]
            if committee_work.status.selector == SHARD_WORK_CONFIRMED:
                commitment: DataCommitment = committee_work.status.value
                # Charge EIP 1559 fee
                proposer = get_shard_proposer_index(state, slot, Shard(shard_index))
                fee = (
                    (state.shard_gasprice * commitment.length)
                    // TARGET_SAMPLES_PER_BLOCK
                )
                decrease_balance(state, proposer, fee)

                # Track updated gas price
                new_gasprice = compute_updated_gasprice(
                    new_gasprice,
                    commitment.length,
                    adjustment_quotient,
                )
    state.shard_gasprice = new_gasprice
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
                        commitment=DataCommitment(),
                        root=Root(),
                        votes=Bitlist[MAX_VALIDATORS_PER_COMMITTEE]([0] * committee_length),
                        weight=0,
                        update_slot=slot,
                    )
                )
            )
        # a shard without committee available defaults to SHARD_WORK_UNCONFIRMED.
```

#### `process_shard_epoch_increment`

```python
def process_shard_epoch_increment(state: BeaconState) -> None:
    # Update current_epoch_start_shard
    state.current_epoch_start_shard = get_start_shard(state, Slot(state.slot + 1))
```
