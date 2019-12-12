# Phase 1 miscellaneous beacon chain changes

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Configuration](#configuration)
- [Containers](#containers)
    - [`CompactCommittee`](#compactcommittee)
    - [`ShardReceiptDelta`](#shardreceiptdelta)
    - [`ShardReceiptProof`](#shardreceiptproof)
- [Helper functions](#helper-functions)
    - [`pack_compact_validator`](#pack_compact_validator)
    - [`unpack_compact_validator`](#unpack_compact_validator)
    - [`committee_to_compact_committee`](#committee_to_compact_committee)
    - [`verify_merkle_proof`](#verify_merkle_proof)
    - [`compute_historical_state_generalized_index`](#compute_historical_state_generalized_index)
    - [`get_generalized_index_of_crosslink_header`](#get_generalized_index_of_crosslink_header)
    - [`process_shard_receipt_proof`](#process_shard_receipt_proof)
- [Changes](#changes)
  - [Phase 0 container updates](#phase-0-container-updates)
    - [`BeaconState`](#beaconstate)
    - [`BeaconBlockBody`](#beaconblockbody)
  - [Persistent committees](#persistent-committees)
  - [Shard receipt processing](#shard-receipt-processing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Configuration

| Name | Value | Unit | Duration
| - | - | - | - |
| `MAX_SHARD_RECEIPT_PROOFS` | `2**0` (= 1) | - | - |
| `PERIOD_COMMITTEE_ROOT_LENGTH` | `2**8` (= 256) | periods | ~9 months |
| `MINOR_REWARD_QUOTIENT` | `2**8` (=256) | - | - |
| `REWARD_COEFFICIENT_BASE` | **TBD** | - | - |

## Containers

#### `CompactCommittee`

```python
class CompactCommittee(Container):
    pubkeys: List[BLSPubkey, MAX_VALIDATORS_PER_COMMITTEE]
    compact_validators: List[uint64, MAX_VALIDATORS_PER_COMMITTEE]
```

#### `ShardReceiptDelta`

```python
class ShardReceiptDelta(Container):
    index: ValidatorIndex
    reward_coefficient: uint64
    block_fee: Gwei
```


#### `ShardReceiptProof`

```python
class ShardReceiptProof(Container):
    shard: Shard
    proof: List[Bytes32, PLACEHOLDER]
    receipt: List[ShardReceiptDelta, PLACEHOLDER]
```

## Helper functions

#### `pack_compact_validator`

```python
def pack_compact_validator(index: int, slashed: bool, balance_in_increments: int) -> int:
    """
    Creates a compact validator object representing index, slashed status, and compressed balance.
    Takes as input balance-in-increments (// EFFECTIVE_BALANCE_INCREMENT) to preserve symmetry with
    the unpacking function.
    """
    return (index << 16) + (slashed << 15) + balance_in_increments
```

#### `unpack_compact_validator`

```python
def unpack_compact_validator(compact_validator: int) -> Tuple[int, bool, int]:
    """
    Returns validator index, slashed, balance // EFFECTIVE_BALANCE_INCREMENT
    """
    return compact_validator >> 16, bool((compact_validator >> 15) % 2), compact_validator & (2**15 - 1)
```

#### `committee_to_compact_committee`

```python
def committee_to_compact_committee(state: BeaconState, committee: Sequence[ValidatorIndex]) -> CompactCommittee:
    """
    Given a state and a list of validator indices, outputs the CompactCommittee representing them.
    """
    validators = [state.validators[i] for i in committee]
    compact_validators = [
        pack_compact_validator(i, v.slashed, v.effective_balance // EFFECTIVE_BALANCE_INCREMENT)
        for i, v in zip(committee, validators)
    ]
    pubkeys = [v.pubkey for v in validators]
    return CompactCommittee(pubkeys=pubkeys, compact_validators=compact_validators)
```

#### `verify_merkle_proof`

```python
def verify_merkle_proof(leaf: Bytes32, proof: Sequence[Bytes32], index: GeneralizedIndex, root: Root) -> bool:
    assert len(proof) == get_generalized_index_length(index)
    for i, h in enumerate(proof):
        if get_generalized_index_bit(index, i):
            leaf = hash(h + leaf)
        else:
            leaf = hash(leaf + h)
    return leaf == root
```

#### `compute_historical_state_generalized_index`

```python
def compute_historical_state_generalized_index(earlier: ShardSlot, later: ShardSlot) -> GeneralizedIndex:
    """
    Computes the generalized index of the state root of slot `earlier` based on the state root of slot `later`.
    Relies on the `history_accumulator` in the `ShardState`, where `history_accumulator[i]` maintains the most
    recent 2**i'th slot state. Works by tracing a `log(later-earlier)` step path from `later` to `earlier`
    through intermediate blocks at the next available multiples of descending powers of two.
    """
    o = GeneralizedIndex(1)
    for i in range(HISTORY_ACCUMULATOR_DEPTH - 1, -1, -1):
        if (later - 1) & 2**i > (earlier - 1) & 2**i:
            later = later - ((later - 1) % 2**i) - 1
            gindex = GeneralizedIndex(get_generalized_index(ShardState, ['history_accumulator', i]))
            o = concat_generalized_indices(o, gindex)
    return o
```

#### `get_generalized_index_of_crosslink_header`

```python
def get_generalized_index_of_crosslink_header(index: int) -> GeneralizedIndex:
    """
    Gets the generalized index for the root of the index'th header in a crosslink.
    """
    MAX_CROSSLINK_SIZE = (
        MAX_SHARD_BLOCK_SIZE * SHARD_SLOTS_PER_EPOCH * MAX_EPOCHS_PER_CROSSLINK
    )
    assert MAX_CROSSLINK_SIZE == get_previous_power_of_two(MAX_CROSSLINK_SIZE)
    return GeneralizedIndex(MAX_CROSSLINK_SIZE // SHARD_HEADER_SIZE + index)
```

#### `process_shard_receipt_proof`

```python
def process_shard_receipt_proof(state: BeaconState, receipt_proof: ShardReceiptProof) -> None:
    """
    Processes a ShardReceipt object.
    """
    receipt_slot = (
        state.next_shard_receipt_period[receipt_proof.shard] *
        SHARD_SLOTS_PER_EPOCH * EPOCHS_PER_SHARD_PERIOD
    )
    first_slot_in_last_crosslink = state.current_crosslinks[receipt_proof.shard].start_epoch * SHARD_SLOTS_PER_EPOCH
    gindex = concat_generalized_indices(
        get_generalized_index_of_crosslink_header(0),
        GeneralizedIndex(get_generalized_index(ShardBlockHeader, 'state_root')),
        compute_historical_state_generalized_index(receipt_slot, first_slot_in_last_crosslink),
        GeneralizedIndex(get_generalized_index(ShardState, 'receipt_root'))
    )
    assert verify_merkle_proof(
        leaf=hash_tree_root(receipt_proof.receipt),
        proof=receipt_proof.proof,
        index=gindex,
        root=state.current_crosslinks[receipt_proof.shard].data_root
    )
    for delta in receipt_proof.receipt:
        if get_current_epoch(state) < state.validators[delta.index].withdrawable_epoch:
            increase_amount = (
                state.validators[delta.index].effective_balance * delta.reward_coefficient // REWARD_COEFFICIENT_BASE
            )
            increase_balance(state, delta.index, increase_amount)
            decrease_balance(state, delta.index, delta.block_fee)
    state.next_shard_receipt_period[receipt_proof.shard] += 1
    proposer_index = get_beacon_proposer_index(state)
    increase_balance(state, proposer_index, Gwei(get_base_reward(state, proposer_index) // MINOR_REWARD_QUOTIENT))
```

## Changes

### Phase 0 container updates

Add the following fields to the end of the specified container objects.

#### `BeaconState`

```python
class BeaconState(Container):
    # Period committees
    period_committee_roots: Vector[Root, PERIOD_COMMITTEE_ROOT_LENGTH]
    next_shard_receipt_period: Vector[uint64, SHARD_COUNT]
```

`period_committee_roots` values are initialized to `Bytes32()` (empty bytes value).
`next_shard_receipt_period` values are initialized to `compute_epoch_at_slot(PHASE_1_FORK_SLOT) // EPOCHS_PER_SHARD_PERIOD`.

#### `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    shard_receipt_proofs: List[ShardReceiptProof, MAX_SHARD_RECEIPT_PROOFS]
```

`shard_receipt_proofs` is initialized to `[]`.

### Persistent committees

Run `update_period_committee` immediately before `process_final_updates`:

```python
# begin insert @update_period_committee
    update_period_committee(state)
# end insert @update_period_committee
def update_period_committee(state: BeaconState) -> None:
    """
    Updates period committee roots at boundary blocks.
    """
    if (get_current_epoch(state) + 1) % EPOCHS_PER_SHARD_PERIOD != 0:
        return

    period = (get_current_epoch(state) + 1) // EPOCHS_PER_SHARD_PERIOD
    committees = Vector[CompactCommittee, SHARD_COUNT]([
        committee_to_compact_committee(
            state,
            get_period_committee(state, Shard(shard), Epoch(get_current_epoch(state) + 1)),
        )
        for shard in range(SHARD_COUNT)
    ])
    state.period_committee_roots[period % PERIOD_COMMITTEE_ROOT_LENGTH] = hash_tree_root(committees)
```

### Shard receipt processing

Run `process_shard_receipt_proof` on each `ShardReceiptProof` during block processing.

```python
# begin insert @process_shard_receipt_proofs
        (body.shard_receipt_proofs, process_shard_receipt_proof),
# end insert @process_shard_receipt_proofs
```
