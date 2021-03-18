# Ethereum 2.0 Sharding -- Beacon Chain changes 

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Configuration](#configuration)
  - [Misc](#misc)
  - [Shard block configs](#shard-block-configs)
  - [Precomputed size verification points](#precomputed-size-verification-points)
  - [Gwei values](#gwei-values)
  - [Time parameters](#time-parameters)
  - [Domain types](#domain-types)
- [Updated containers](#updated-containers)
  - [`AttestationData`](#attestationdata)
  - [`BeaconBlockBody`](#beaconblockbody)
  - [`BeaconState`](#beaconstate)
- [New containers](#new-containers)
  - [`DataCommitment`](#datacommitment)
  - [`ShardHeader`](#shardheader)
  - [`SignedShardHeader`](#signedshardheader)
  - [`PendingShardHeader`](#pendingshardheader)
- [Helper functions](#helper-functions)
  - [Misc](#misc-1)
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
  - [New Attestation processing](#new-attestation-processing)
    - [Updated `process_attestation`](#updated-process_attestation)
    - [`update_pending_votes`](#update_pending_votes)
    - [`process_shard_header`](#process_shard_header)
  - [Epoch transition](#epoch-transition)
    - [Pending headers](#pending-headers)
    - [Shard epoch increment](#shard-epoch-increment)

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
| `BLSCommitment` | `bytes48` | A G1 curve point |
| `BLSPoint` | `uint256` | A number `x` in the range `0 <= x < MODULUS` |

## Configuration

### Misc

| Name | Value | Notes |
| - | - | - |
| `MAX_SHARDS` | `uint64(2**10)` (= 1024) | Theoretical max shard count (used to determine data structure sizes) |
| `INITIAL_ACTIVE_SHARDS` | `uint64(2**6)` (= 64) | Initial shard count |
| `GASPRICE_ADJUSTMENT_COEFFICIENT` | `uint64(2**3)` (= 8) | Gasprice may decrease/increase by at most exp(1 / this value) *per epoch* |
| `MAX_SHARD_HEADERS_PER_SHARD` | `4` | |
| `MAX_SHARD_HEADERS` | `MAX_SHARDS * MAX_SHARD_HEADERS_PER_SHARD` | |
| `PRIMITIVE_ROOT_OF_UNITY` | `5` | Primitive root of unity of the BLS12_381 (inner) modulus |
| `DATA_AVAILABILITY_INVERSE_CODING_RATE` | `2**1` (=2) | Factor by which samples are extended for data availability encoding |


### Shard block configs

| Name | Value | Notes |
| - | - | - |
| `POINTS_PER_SAMPLE` | `uint64(2**3)` (= 8) | 31 * 8 = 248 bytes |
| `MAX_SAMPLES_PER_BLOCK` | `uint64(2**11)` (= 2,048) | 248 * 2,048 = 507,904 bytes |
| `TARGET_SAMPLES_PER_BLOCK` | `uint64(2**10)` (= 1,024) | 248 * 1,024 = 253,952 bytes |

### Precomputed size verification points

| Name | Value |
| - | - |
| `G1_SETUP` | Type `List[G1]`. The G1-side trusted setup `[G, G*s, G*s**2....]`; note that the first point is the generator. |
| `G2_SETUP` | Type `List[G2]`. The G2-side trusted setup `[G, G*s, G*s**2....]` |
| `MODULUS` | `0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001` (curve order of BLS12_381) |
| `ROOT_OF_UNITY` | `pow(PRIMITIVE_ROOT_OF_UNITY, (MODULUS - 1) // (MAX_SAMPLES_PER_BLOCK * POINTS_PER_SAMPLE, MODULUS)` |

### Gwei values

| Name | Value | Unit | Description |
| - | - | - | - |
| `MAX_GASPRICE` | `Gwei(2**33)` (= 8,589,934,592) | Gwei | Max gasprice charged for a TARGET-sized shard block |  
| `MIN_GASPRICE` | `Gwei(2**3)` (= 8) | Gwei | Min gasprice charged for a TARGET-sized shard block |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SHARD_COMMITTEE_PERIOD` | `Epoch(2**8)` (= 256) | epochs | ~27 hours |

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_SHARD_HEADER` | `DomainType('0x80000000')` |
| `DOMAIN_SHARD_COMMITTEE` | `DomainType('0x81000000')` |

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
    shard_header_root: Root
```

### `BeaconBlockBody`

```python
class BeaconBlockBody(phase0.BeaconBlockBody):
    # insert phase 0 fields
    shard_headers: List[SignedShardHeader, MAX_SHARD_HEADERS]
```

### `BeaconState`

```python
class BeaconState(phase0.BeaconState):
    # Updated fields
    previous_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    current_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    # New fields
    previous_epoch_pending_shard_headers: List[PendingShardHeader, MAX_SHARD_HEADERS * SLOTS_PER_EPOCH]
    current_epoch_pending_shard_headers: List[PendingShardHeader, MAX_SHARD_HEADERS * SLOTS_PER_EPOCH]
    grandparent_epoch_confirmed_commitments: Vector[Vector[DataCommitment, SLOTS_PER_EPOCH], MAX_SHARDS]
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

### `ShardHeader`

```python
class ShardHeader(Container):
    # Slot and shard that this header is intended for
    slot: Slot
    shard: Shard
    # The actual data commitment
    commitment: DataCommitment
    # Proof that the degree < commitment.length
    degree_proof: BLSCommitment
```

TODO: add shard-proposer-index to shard headers, similar to optimization done with beacon-blocks.

### `SignedShardHeader`

```python
class SignedShardHeader(Container):
    message: ShardHeader
    signature: BLSSignature
```

### `PendingShardHeader`

```python
class PendingShardHeader(Container):
    # Slot and shard that this header is intended for
    slot: Slot
    shard: Shard
    # KZG10 commitment to the data
    commitment: DataCommitment
    # hash_tree_root of the ShardHeader (stored so that attestations can be checked against it)
    root: Root
    # Who voted for the header
    votes: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    # Has this header been confirmed?
    confirmed: bool
```

## Helper functions

### Misc

#### `next_power_of_two`

```python
def next_power_of_two(x):
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
                           min_effective_balance: GWei = GWei(0)) -> ValidatorIndex:
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
    seed = hash(get_seed(beacon_state, epoch, DOMAIN_BEACON_PROPOSER) + uint_to_bytes(beacon_state.slot))

    # Proposer must have sufficient balance to pay for worst case fee burn
    EFFECTIVE_BALANCE_MAX_DOWNWARD_DEVIATION = (
        (EFFECTIVE_BALANCE_INCREMENT - EFFECTIVE_BALANCE_INCREMENT)
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
    return Shard((index + get_start_shard(state, slot)) % active_shards)
```

#### `compute_committee_index_from_shard`

```python
def compute_committee_index_from_shard(state: BeaconState, slot: Slot, shard: Shard) -> CommitteeIndex:
    active_shards = get_active_shard_count(state, compute_epoch_at_slot(slot))
    return CommitteeIndex((active_shards + shard - get_start_shard(state, slot)) % active_shards)    
```


### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_light_client_aggregate(state, block.body)
    process_operations(state, block.body)
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
    # Limit is dynamic based on active shard count
    assert len(body.shard_headers) <= MAX_SHARD_HEADERS_PER_SHARD * get_active_shard_count(state, get_current_epoch(state))
    for_ops(body.shard_headers, process_shard_header)
    # New attestation processing
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)
```

### New Attestation processing

#### Updated `process_attestation`

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    phase0.process_attestation(state, attestation)
    update_pending_votes(state, attestation)
```

#### `update_pending_votes`

```python
def update_pending_votes(state: BeaconState, attestation: Attestation) -> None:
    # Find and update the PendingShardHeader object, invalid block if pending header not in state
    if compute_epoch_at_slot(attestation.data.slot) == get_current_epoch(state):
        pending_headers = state.current_epoch_pending_shard_headers
    else:
        pending_headers = state.previous_epoch_pending_shard_headers
    pending_header = None
    for header in pending_headers:
        if header.root == attestation.data.shard_header_root:
            pending_header = header
    assert pending_header is not None
    assert pending_header.slot == attestation.data.slot
    assert pending_header.shard == compute_shard_from_committee_index(
        state,
        attestation.data.slot,
        attestation.data.index,
    )
    for i in range(len(pending_header.votes)):
        pending_header.votes[i] = pending_header.votes[i] or attestation.aggregation_bits[i]

    # Check if the PendingShardHeader is eligible for expedited confirmation
    # Requirement 1: nothing else confirmed
    all_candidates = [
        c for c in pending_headers if
        (c.slot, c.shard) == (pending_header.slot, pending_header.shard)
    ]
    if True in [c.confirmed for c in all_candidates]:
        return

    # Requirement 2: >= 2/3 of balance attesting
    participants = get_attesting_indices(state, attestation.data, pending_header.votes)
    participants_balance = get_total_balance(state, participants)
    full_committee = get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    full_committee_balance = get_total_balance(state, full_committee)
    if participants_balance * 3 >= full_committee_balance * 2:
        pending_header.confirmed = True
```

#### `process_shard_header`

```python
def process_shard_header(state: BeaconState,
                         signed_header: SignedShardHeader) -> None:
    header = signed_header.message
    header_root = hash_tree_root(header)
    assert compute_epoch_at_slot(header.slot) in [get_previous_epoch(state), get_current_epoch(state)]

    # Verify signature
    signer_index = get_shard_proposer_index(state, header.slot, header.shard)
    signing_root = compute_signing_root(header, get_domain(state, DOMAIN_SHARD_HEADER))
    assert bls.Verify(state.validators[signer_index].pubkey, signing_root, signed_header.signature)

    # Verify the length by verifying the degree.
    if header.commitment.length == 0:
        assert header.degree_proof == G1_SETUP[0]
    assert (
        bls.Pairing(header.degree_proof, G2_SETUP[0])
        == bls.Pairing(header.commitment.point, G2_SETUP[-header.commitment.length]))
    )

    # Get the correct pending header list
    if compute_epoch_at_slot(header.slot) == get_current_epoch(state):
        pending_headers = state.current_epoch_pending_shard_headers
    else:
        pending_headers = state.previous_epoch_pending_shard_headers

    # Check that this header is not yet in the pending list
    assert header_root not in [pending_header.root for pending_header in pending_headers]

    # Include it in the pending list
    index = compute_committee_index_from_shard(state, header.slot, header.shard)
    committee_length = len(get_beacon_committee(state, header.slot, index))
    pending_headers.append(PendingShardHeader(
        slot=header.slot,
        shard=header.shard,
        commitment=header.commitment,
        root=header_root,
        votes=Bitlist[MAX_VALIDATORS_PER_COMMITTEE]([0] * committee_length),
        confirmed=False,
    ))
```

The degree proof works as follows. For a block `B` with length `l` (so `l`  values in `[0...l - 1]`, seen as a polynomial `B(X)` which takes these values),
the length proof is the commitment to the polynomial `B(X) * X**(MAX_DEGREE + 1 - l)`,
where `MAX_DEGREE` is the maximum power of `s` available in the setup, which is `MAX_DEGREE = len(G2_SETUP) - 1`.
The goal is to ensure that a proof can only be constructed if `deg(B) < l` (there are not hidden higher-order terms in the polynomial, which would thwart reconstruction).

### Epoch transition

This epoch transition overrides the phase0 epoch transition:

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)

    process_slashings(state)

    # Sharding
    process_pending_headers(state)
    charge_confirmed_header_fees(state)
    reset_pending_headers(state)

    # Final updates
    # Phase 0
    process_eth1_data_reset(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_roots_update(state)
    process_participation_record_updates(state)

    process_shard_epoch_increment(state)
```

#### Pending headers

```python

def process_pending_headers(state: BeaconState) -> None:
    # Pending header processing applies to the previous epoch.
    # Skip if `GENESIS_EPOCH` because no prior epoch to process.
    if get_current_epoch(state) == GENESIS_EPOCH:
        return

    previous_epoch_start_slot = compute_start_slot_at_epoch(get_previous_epoch(state))
    for slot in range(previous_epoch_start_slot, previous_epoch_start_slot + SLOTS_PER_EPOCH):
        for shard in range(get_active_shard_count(state)):
            # Pending headers for this (slot, shard) combo
            candidates = [
                c for c in state.previous_epoch_pending_shard_headers
                if (c.slot, c.shard) == (slot, shard)
            ]
            # The entire committee (and its balance)
            full_committee = get_beacon_committee(state, slot, shard)
            full_committee_balance = get_total_balance(state, full_committee)
            # If any candidates already confirmed, skip
            if True in [c.confirmed for c in candidates]:
                continue

            # The set of voters who voted for each header (and their total balances)
            voting_sets = [
                [v for i, v in enumerate(full_committee) if c.votes[i]]
                for c in candidates
            ]
            voting_balances = [
                get_total_balance(state, voters)
                for voters in voting_sets
            ]
            # Get the index with the most total balance voting for them.
            # NOTE: if two choices get exactly the same voting balance,
            # the candidate earlier in the list wins
            if max(voting_balances) > 0:
                winning_index = voting_balances.index(max(voting_balances))
            else:
                # If no votes, zero wins
                winning_index = [c.root for c in candidates].index(Root())
            candidates[winning_index].confirmed = True
    for slot_index in range(SLOTS_PER_EPOCH):
        for shard in range(SHARD_COUNT):
            state.grandparent_epoch_confirmed_commitments[shard][slot_index] = DataCommitment()
    confirmed_headers = [candidate in state.previous_epoch_pending_shard_headers if candidate.confirmed]
    for header in confirmed_headers:
        state.grandparent_epoch_confirmed_commitments[c.shard][c.slot % SLOTS_PER_EPOCH] = c.commitment
```

```python
def charge_confirmed_header_fees(state: BeaconState) -> None:
    new_gasprice = state.shard_gasprice
    adjustment_quotient = (
        get_active_shard_count(state, get_current_epoch(state))
        * SLOTS_PER_EPOCH * GASPRICE_ADJUSTMENT_COEFFICIENT
    )
    previous_epoch_start_slot = compute_start_slot_at_epoch(get_previous_epoch(state))
    for slot in range(previous_epoch_start_slot, previous_epoch_start_slot + SLOTS_PER_EPOCH):
        for shard in range(SHARD_COUNT):
            confirmed_candidates = [
                c for c in state.previous_epoch_pending_shard_headers
                if (c.slot, c.shard, c.confirmed) == (slot, shard, True)
            ]
            if not any(confirmed_candidates):
                continue
            candidate = confirmed_candidates[0]

            # Charge EIP 1559 fee
            proposer = get_shard_proposer(state, slot, shard)
            fee = (
                (state.shard_gasprice * candidate.commitment.length)
                // TARGET_SAMPLES_PER_BLOCK
            )
            decrease_balance(state, proposer, fee)

            # Track updated gas price
            new_gasprice = compute_updated_gasprice(
                new_gasprice,
                candidate.commitment.length,
                adjustment_quotient,
            )
    state.shard_gasprice = new_gasprice
```

```python
def reset_pending_headers(state: BeaconState) -> None:
    state.previous_epoch_pending_shard_headers = state.current_epoch_pending_shard_headers
    state.current_epoch_pending_shard_headers = []
    # Add dummy "empty" PendingShardHeader (default vote for if no shard header available)
    next_epoch = get_current_epoch(state) + 1
    next_epoch_start_slot = compute_start_slot_at_epoch(next_epoch)
    for slot in range(next_epoch_start_slot, next_epoch_start_slot + SLOTS_IN_EPOCH):
        for index in range(get_committee_count_per_slot(next_epoch)
            shard = compute_shard_from_committee_index(state, slot, index)
            committee_length = len(get_beacon_committee(state, slot, shard))
            state.current_epoch_pending_shard_headers.append(PendingShardHeader(
                slot=slot,
                shard=shard,
                commitment=DataCommitment(),
                root=Root(),
                votes=Bitlist[MAX_VALIDATORS_PER_COMMITTEE]([0] * committee_length),
                confirmed=False,
            ))
```

#### Shard epoch increment

```python
def process_shard_epoch_increment(state: BeaconState) -> None:
    # Update current_epoch_start_shard
    state.current_epoch_start_shard = get_start_shard(state, Slot(state.slot + 1))
```
