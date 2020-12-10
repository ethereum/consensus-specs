# Ethereum 2.0 Phase 1 -- The Beacon Chain with Shards

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Configuration](#configuration)
- [Updated containers](#updated-containers)
- [New containers](#new-containers)
- [Helper functions](#helper-functions)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes the extensions made to the Phase 0 design of The Beacon Chain to support data sharding, based on the ideas [here](https://hackmd.io/@HWeNw8hNRimMm2m2GH56Cw/r1XzqYIOv) and more broadly [here](https://arxiv.org/abs/1809.09044), using Kate commitments to commit to data to remove any need for fraud proofs (and hence, safety-critical synchrony assumptions) in the design.

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `Shard` | `uint64` | A shard number |
| `BLSCommitment` | `bytes48` | A G1 curve point |

## Configuration

### Misc

| Name | Value | Notes |
| - | - | - |
| `MAX_SHARDS` | `uint64(2**10)` (= 1024) | Theoretical max shard count (used to determine data structure sizes) |
| `INITIAL_ACTIVE_SHARDS` | `uint64(2**6)` (= 64) | Initial shard count |
| `GASPRICE_ADJUSTMENT_COEFFICIENT` | `uint64(2**3)` (= 2) | Gasprice may decrease/increase by at most exp(1 / this value) *per epoch* |
| `MAX_SHARD_HEADERS` | `MAX_SHARDS * 4` | |

### Shard block configs

| Name | Value | Notes |
| - | - | - |
| `POINTS_PER_SAMPLE` | `uint64(2**3)` (= 8) | 31 * 8 = 248 bytes |
| `MAX_SAMPLES_PER_BLOCK` | `uint64(2**11)` (= 2,048) | 248 * 2,048 = 507,904 bytes |
| `TARGET_SAMPLES_PER_BLOCK` | `uint64(2**10)` (= 1,024) | 248 * 1,024 = 253,952 bytes |

### Precomputed size verification points

| Name | Value |
| - | - |
| `G2_ONE` | The G2 generator |
| `SIZE_CHECK_POINTS` | Type `List[G2, MAX_SAMPLES_PER_BLOCK + 1]`; TO BE COMPUTED |

These points are the G2-side Kate commitments to `product[a in i...MAX_SAMPLES_PER_BLOCK] (X - w ** revbit(a))` for each `i` in `[0...MAX_SAMPLES_PER_BLOCK]`, where `w` is the root of unity and `revbit` is the reverse-bit-order function. They are used to verify block size proofs. They can be computed with a one-time O(N^2/log(N)) calculation using fast-linear-combinations in G2.

### Gwei values

| Name | Value | Unit | Description |
| - | - | - | - |
| `MAX_GASPRICE` | `Gwei(2**24)` (= 16,777,216) | Gwei | Max gasprice charged for an TARGET-sized shard block |  
| `MIN_GASPRICE` | `Gwei(2**3)` (= 8) | Gwei | Min gasprice charged for an TARGET-sized shard block |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SHARD_COMMITTEE_PERIOD` | `Epoch(2**8)` (= 256) | epochs | ~27 hours |

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_SHARD_HEADER` | `DomainType('0x80000000')` |

## Updated containers

The following containers have updated definitions in Phase 1.

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

### `BeaconBlock`

```python
class BeaconBlock(phase0.BeaconBlock):
    shard_headers: List[Signed[ShardHeader], MAX_SHARD_HEADERS]
```

### `BeaconState`

```python
class BeaconState(phase0.BeaconState):
    current_epoch_pending_headers: List[PendingHeader, MAX_PENDING_HEADERS * SLOTS_PER_EPOCH]
    previous_epoch_pending_headers: List[PendingHeader, MAX_PENDING_HEADERS * SLOTS_PER_EPOCH]
    two_epochs_ago_confirmed_headers: Vector[Vector[PendingShardHeader, SLOTS_PER_EPOCH], MAX_SHARDS]
    shard_gasprice: uint64
    current_epoch_start_shard: Shard
```

## New containers

The following containers are new in Phase 1.

### `ShardHeader`

```python
class ShardHeader(Container):
    # Slot and shard that this header is intended for
    slot: Slot
    shard: Shard
    # Kate commitment to the data
    commitment: BLSCommitment
    # Length of the data in samples
    length: uint64
    # Proof of the length (more precisely, proof that values at
    # positions >= the length all equal zero)
    length_proof: BLSCommitment
```

### `PendingShardHeader`

```python
class PendingShardHeader(Container):
    # Slot and shard that this header is intended for
    slot: uint64
    shard: Shard
    # Kate commitment to the data
    commitment: BLSCommitment
    # hash_tree_root of the ShardHeader (stored so that attestations
    # can be checked against it)
    root: Hash
    # Length of the data in samples
    length: uint64
    # Who voted for the header
    votes: Bitlist[MAX_COMMITTEE_SIZE]
    # Has this header been confirmed?
    confirmed: bool
```

## Helper functions

### Misc

#### `compute_previous_slot`

```python
def compute_previous_slot(slot: Slot) -> Slot:
    if slot > 0:
        return Slot(slot - 1)
    else:
        return Slot(0)
```

#### `compute_shard_from_committee_index`

```python
def compute_shard_from_committee_index(state: BeaconState, index: CommitteeIndex, slot: Slot) -> Shard:
    active_shards = get_active_shard_count(state)
    return Shard((index + get_start_shard(state, slot)) % active_shards)
```

#### `compute_updated_gasprice`

```python
def compute_updated_gasprice(prev_gasprice: Gwei, shard_block_length: uint64, adjustment_quotient: uint64) -> Gwei:
    if shard_block_length > TARGET_SAMPLES_PER_BLOCK:
        delta = (prev_gasprice * (shard_block_length - TARGET_SAMPLES_PER_BLOCK)
                 // TARGET_SAMPLES_PER_BLOCK // adjustment_quotient)
        return min(prev_gasprice + delta, MAX_GASPRICE)
    else:
        delta = (prev_gasprice * (TARGET_SAMPLES_PER_BLOCK - shard_block_length)
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

#### `get_shard_proposer_index`

```python
def get_shard_proposer_index(beacon_state: BeaconState, slot: Slot, shard: Shard) -> ValidatorIndex:
    """
    Return the proposer's index of shard block at ``slot``.
    """
    epoch = compute_epoch_at_slot(slot)
    committee = get_shard_committee(beacon_state, epoch, shard)
    seed = hash(get_seed(beacon_state, epoch, DOMAIN_SHARD_COMMITTEE) + uint_to_bytes(slot))
    return compute_proposer_index(state, committee, seed)
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
        return Shard(shard)
    elif slot < current_epoch_start_slot:
        # Previous epoch
        for _slot in list(range(slot, current_epoch_start_slot))[::-1]:
            committee_count = get_committee_count_per_slot(state, compute_epoch_at_slot(Slot(_slot)))
            active_shard_count = get_active_shard_count(state, compute_epoch_at_slot(Slot(_slot)))
            # Ensure positive
            shard = (shard + active_shard_count - committee_count) % active_shard_count
    return Shard(shard)
```

### Predicates

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
    # New attestation processing
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    # Limit is dynamic based on active shard count
    assert len(body.shard_headers) <= 4 * get_active_shard_count(state, get_current_epoch(state))
    for_ops(body.shard_headers, process_shard_header)

    # See custody game spec.
    process_custody_game_operations(state, body)

    process_shard_transitions(state, body.shard_transitions, body.attestations)

    # TODO process_operations(body.shard_receipt_proofs, process_shard_receipt_proofs)
```

### New Attestation processing

#### Updated `process_attestation`

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    phase0.process_attestation(state, attestation)
    update_pending_votes(
        state=state,
        attestation: Attestation,
        root=,
        aggregation_bits=attestation.aggregation_bits
    )
```

#### `update_pending_votes`

```python
def update_pending_votes(state: BeaconState,
                         attestation: Attestation) -> None:
    if compute_epoch_at_slot(slot) == get_current_epoch(state):
        pending_headers = state.current_epoch_pending_headers
    else:
        pending_headers = state.previous_epoch_pending_headers
    # Create or update the PendingShardHeader object
    pending_header = None
    for header in pending_headers:
        if header.root == attestation.data.shard_header_root:
            pending_header = header
    assert pending_header is not None
    assert pending_header.slot == attestation.data.slot + 1
    assert pending_header.shard == compute_shard_from_committee_index(
        state,
        attestation.data.index,
        attestation.data.slot
    )
    pending_header.votes = bitwise_or(
        pending_header.votes,
        attestation.aggregation_bits
    )

    # Check if the PendingShardHeader is eligible for expedited confirmation
    # Requirement 1: nothing else confirmed
    all_candidates = [
        c for c in pending_headers if
        (c.slot, c.shard) == (pending_header.slot, pending_header.shard)
    ]
    if True not in [c.confirmed for c in all_candidates]:
        # Requirement 2: >= 2/3 of balance attesting
        participants = get_attesting_indices(state, data, pending_commitment.votes)
        participants_balance = get_total_balance(state, participants)
        full_committee = get_beacon_committee(state, data.slot, data.shard)
        full_committee_balance = get_total_balance(state, full_committee)
        if participants_balance * 2 > full_committee_balance:
            pending_header.confirmed = True
```

#### `process_shard_header`

```python
def process_shard_header(state: BeaconState,
                         signed_header: Signed[ShardDataHeader]) -> None:
    header = signed_header.message
    header_root = hash_tree_root(header)
    # Verify signature
    signer_index = get_shard_proposer_index(state, header.slot, header.shard)
    assert bls.Verify(
        state.validators[signer_index].pubkey,
        compute_signing_root(header, get_domain(state, DOMAIN_SHARD_HEADER)),
        signed_header.signature
    )
    # Verify length of the header
    assert (
        bls.Pairing(header.length_proof, SIZE_CHECK_POINTS[header.length]) ==
        bls.Pairing(header.commitment, G2_ONE)
    )
    # Get the correct pending header list
    if compute_epoch_at_slot(header.slot) == get_current_epoch(state):
        pending_headers = state.current_epoch_pending_headers
    else:
        pending_headers = state.previous_epoch_pending_headers
        
    # Check that this header is not yet in the pending list
    for pending_header in pending_headers:
        assert header_root != pending_header.root
    # Include it in the pending list
    committee_length = len(get_beacon_committee(state, header.slot, header.shard))
    pending_headers.append(PendingShardHeader(
        slot=header.slot,
        shard=header.shard,
        commitment=header.commitment,
        root=header_root,
        length=header.length,
        votes=Bitlist[MAX_COMMITTEE_SIZE]([0] * committee_length),
        confirmed=False
    ))
```

### Shard transition processing

### Epoch transition

This epoch transition overrides the phase0 epoch transition:

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)

    # Proof of custody
    process_reveal_deadlines(state)
    process_challenge_deadlines(state)

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
    # Proof of custody
    process_custody_final_updates(state)
    # Update current_epoch_start_shard
    state.current_epoch_start_shard = get_start_shard(state, Slot(state.slot + 1))
```

#### Pending headers

```python

def process_pending_headers(state: BeaconState):
    for slot in range(SLOTS_PER_EPOCH):
        for shard in range(SHARD_COUNT):
            # Pending headers for this (slot, shard) combo
            candidates = [
                c for c in state.previous_epoch_pending_headers if
                (c.slot, c.shard) == (slot, shard)
            ]
            if True not in [c.confirmed for c in candidates]:
                # The entire committee (and its balance)
                full_committee = get_beacon_committee(state, slot, shard)
                full_committee_balance = get_total_balance(state, full_committee)
                # The set of voters who voted for each header
                # (and their total balances)
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
    for slot in range(SLOTS_PER_EPOCH):
        for shard in range(SHARD_COUNT):
            state.two_epochs_ago_confirmed_headers[shard][slot] = PendingHeader()
    for c in state.previous_epoch_pending_headers:
        if c.confirmed:
            state.two_epochs_ago_confirmed_headers[c.shard][c.slot % SLOTS_PER_EPOCH] = c
```            

```python
def charge_confirmed_header_fees(state: BeaconState) -> None:
    new_gasprice = state.shard_gasprice
    adjustment_quotient = get_active_shard_count(state) * SLOTS_PER_EPOCH * GASPRICE_ADJUSTMENT_COEFFICIENT
    for slot in range(SLOTS_PER_EPOCH):
        for shard in range(SHARD_COUNT):
            confirmed_candidates = [
                c for c in state.previous_epoch_pending_headers if
                (c.slot, c.shard, c.confirmed) == (slot, shard, True)
            ]
            if confirmed_candidates:
                candidate = confirmed_candidates[0]
                # Charge EIP 1559 fee
                proposer = get_shard_proposer(state, slot, shard)
                fee = (
                    (state.shard_gasprice * candidates[i].length) //
                    TARGET_SAMPLES_PER_BLOCK
                )
                decrease_balance(state, proposer, fee)
                new_gasprice = compute_updated_gasprice(
                    new_gasprice,
                    candidates[i].length,
                    adjustment_quotient
                )
    state.shard_gasprice = new_gasprice
```

```python
def reset_pending_headers(state: BeaconState):
    state.previous_epoch_pending_headers = state.current_epoch_pending_headers
    shards = [
        compute_shard_from_committee_index(state, index, slot)
        for i in range()
        state,
        attestation.data.index,
        attestation.data.slot
    )
    state.current_epoch_pending_headers = []
    # Add dummy "empty" PendingAttestations
    # (default to vote for if no shard header availabl)
    for slot in range(SLOTS_IN_EPOCH):
        for index in range(get_committee_count_per_slot(get_current_epoch(state))):
            shard = compute_shard_from_committee_index(state, index, slot)
            committee_length = len(get_beacon_committee(
                state,
                header.slot,
                header.shard
            ))
            state.current_epoch_pending_headers.append(PendingShardHeader(
                slot=slot,
                shard=shard,
                commitment=BLSCommitment(),
                root=Root(),
                length=0,
                votes=Bitlist[MAX_COMMITTEE_SIZE]([0] * committee_length),
                confirmed=False
            ))

```

#### Custody game updates

`process_reveal_deadlines`, `process_challenge_deadlines` and `process_custody_final_updates` are defined in [the Custody Game spec](./custody-game.md).
