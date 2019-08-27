# Ethereum 2.0 Phase 1 -- Shard Data Chains

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

- [Ethereum 2.0 Phase 1 -- Shard Data Chains](#ethereum-20-phase-1----shard-data-chains)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Custom types](#custom-types)
    - [Configuration](#configuration)
        - [Misc](#misc)
        - [Initial values](#initial-values)
        - [Time parameters](#time-parameters)
        - [State list lengths](#state-list-lengths)
        - [Rewards and penalties](#rewards-and-penalties)
        - [Signature domain types](#signature-domain-types)
    - [Containers](#containers)
        - [`ShardBlockSignatures`](#shardblocksignatures)
        - [`ShardBlock`](#shardblock)
        - [`ShardBlockHeader`](#shardblockheader)
        - [`ShardState`](#shardstate)
        - [`ShardReceiptDelta`](#shardreceiptdelta)
    - [Helper functions](#helper-functions)
        - [Misc](#misc-1)
            - [`pad`](#pad)
            - [`compute_slot_of_shard_slot`](#compute_slot_of_shard_slot)
            - [`compute_epoch_of_shard_slot`](#compute_epoch_of_shard_slot)
            - [`compute_period_start_epoch`](#compute_period_start_epoch)
            - [`compute_flat_shard_header`](#compute_flat_shard_header)
            - [`compute_crosslink_data_root`](#compute_crosslink_data_root)
        - [State accessors](#state-accessors)
            - [`get_period_committee`](#get_period_committee)
            - [`get_persistent_committee`](#get_persistent_committee)
            - [`get_shard_proposer_index`](#get_shard_proposer_index)
            - [`get_default_shard_state`](#get_default_shard_state)
            - [`get_shard_base_reward`](#get_shard_base_reward)
        - [State mutators](#state-mutators)
            - [`add_fee`](#add_fee)
            - [`add_reward`](#add_reward)
    - [Shard state transition function](#shard-state-transition-function)
        - [Period processing](#period-processing)
        - [Block processing](#block-processing)
            - [Block header](#block-header)
            - [Attestations](#attestations)
            - [Block data fees](#block-data-fees)
    - [Object validity](#object-validity)
        - [Shard block validation: preliminary](#shard-block-validation-preliminary)
        - [Beacon attestations](#beacon-attestations)
    - [Shard fork choice rule](#shard-fork-choice-rule)

<!-- /TOC -->

## Introduction

This document describes the shard data layer and the shard fork choice rule in Phase 1 of Ethereum 2.0.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `ShardSlot` | `uint64` | a shard slot number |

## Configuration

### Misc

| Name | Value |
| - | - |
| `SHARD_SLOTS_PER_EPOCH` | `2**7` (= 128) |
| `TARGET_PERSISTENT_COMMITTEE_SIZE` | `2**7` (= 128) |
| `SHARD_HEADER_SIZE` | `2**9` (= 512) |
| `SHARD_BLOCK_SIZE_TARGET` | `2**14` (= 16,384) |
| `SHARD_BLOCK_SIZE_LIMIT` | `2**16` (= 65,536) |

### Initial values

| Name | Value |
| - | - |
| `PHASE_1_FORK_EPOCH` | **TBD** |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `CROSSLINK_LOOKBACK` | `2**0` (= 1) | epochs | 6.4 minutes |
| `EPOCHS_PER_SHARD_PERIOD` | `2**8` (= 256) | epochs | ~27 hours |

### State list lengths

| Name | Value | Unit |
| - | - | :-: |
| `HISTORY_ACCUMULATOR_VECTOR` | `2**6` (= 64) | state tree maximum depth |

### Rewards and penalties

| Name | Value |
| - | - |
| `BASEFEE_ADJUSTMENT_FACTOR` | `2**3` (= 8) |
| `REWARD_COEFFICIENT_BASE` | `2**20` (= 1,048,576) |

### Signature domain types

| Name | Value |
| - | - |
| `DOMAIN_SHARD_PROPOSER` | `128` |
| `DOMAIN_SHARD_ATTESTER` | `129` |

## Containers

### `ShardBlockSignatures`

```python
class ShardBlockSignatures(Container):
    attesters: BLSSignature
    proposer: BLSSignature
```

### `ShardBlock`

```python
class ShardBlock(Container):
    slot: ShardSlot
    beacon_chain_root: Hash
    parent_root: Hash
    state_root: Hash
    aggregation_bits: Bitvector[TARGET_PERSISTENT_COMMITTEE_SIZE * 2]
    total_bytes: uint64
    body: Bytes[SHARD_BLOCK_SIZE_LIMIT - SHARD_HEADER_SIZE]
    padding: Bytes[32]
    signatures: ShardBlockSignatures
```

### `ShardBlockHeader`

```python
class ShardBlockHeader(Container):
    slot: ShardSlot
    beacon_chain_root: Hash
    parent_root: Hash
    state_root: Hash
    aggregation_bits: Bitvector[TARGET_PERSISTENT_COMMITTEE_SIZE * 2]
    total_bytes: uint64
    body_root: Hash
    padding: Bytes[32]
    signatures: ShardBlockSignatures
```

### `ShardState`

```python
class ShardState(Container):
    history_accumulator: Vector[Hash, HISTORY_ACCUMULATOR_VECTOR]
    earlier_committee_rewards: List[uint64, TARGET_PERSISTENT_COMMITTEE_SIZE]
    later_committee_rewards: List[uint64, TARGET_PERSISTENT_COMMITTEE_SIZE]
    earlier_committee_fees: List[Gwei, TARGET_PERSISTENT_COMMITTEE_SIZE]
    later_committee_fees: List[Gwei, TARGET_PERSISTENT_COMMITTEE_SIZE]
    basefee: Gwei
    slot: ShardSlot
    shard: Shard
    latest_block_header: ShardBlockHeader
    receipt_root: Hash
    total_bytes: uint64
```

### `ShardReceiptDelta`

```python
class ShardReceiptDelta(Container):
    index: ValidatorIndex
    reward_coefficient: uint64
    block_fee: Gwei
```

## Helper functions

### Misc

#### `pad`

```python
def pad(x: bytes, length: uint64) -> bytes:
    assert len(x) <= length
    return x + b'\x00' * (length - len(x))
```

#### `compute_epoch_of_shard_slot`

```python
def compute_epoch_of_shard_slot(slot: ShardSlot) -> Epoch:
    return compute_epoch_of_slot(compute_slot_of_shard_slot(slot))
```

#### `compute_period_start_epoch`

```python
def compute_period_start_epoch(epoch: Epoch, lookback: Epoch=0) -> Epoch:
    return Epoch(epoch - (epoch % EPOCHS_PER_SHARD_PERIOD) - lookback * EPOCHS_PER_SHARD_PERIOD)
```

#### `compute_flat_shard_header`

```python
def compute_flat_shard_header(block: ShardBlock) -> Bytes[SHARD_HEADER_SIZE]:
    """
    Return a flat serialisation of the ``block`` header which preserves hash tree root.
    """
    return (
        pad(int_to_bytes(block.slot, length=8), 32) +
        block.beacon_chain_root +
        block.parent_root +
        hash_tree_root(block.body) +
        block.state_root +
        pad(int_to_bytes(block.total_bytes, length=8), 32) +
        bytes([sum([block.aggregation_bits[i + j] << j for j in range(8)]) for i in range(0, 256, 8)]) +
        block.padding +
        pad(block.signatures.attesters, 128) +
        pad(block.signatures.proposer, 128)
    )
```

#### `compute_crosslink_data_root`

```python
def compute_crosslink_data_root(blocks: Sequence[ShardBlock]) -> Hash:
    headers = b''.join([compute_flat_shard_header(block) for block in blocks])
    bodies = b''.join([block.body for block in blocks])
    MAX_SIZE = SHARD_BLOCK_SIZE_LIMIT * SHARD_SLOTS_PER_EPOCH * MAX_EPOCHS_PER_CROSSLINK
    return hash_tree_root(BytesN[MAX_SIZE](pad(headers + bodies, MAX_SIZE)))
```

### State accessors

#### `get_period_committee`

```python
def get_period_committee(state: BeaconState, epoch: Epoch, shard: Shard) -> Sequence[ValidatorIndex]:
    full_committee = compute_committee(
        indices=get_active_validator_indices(state, epoch),
        seed=get_seed(state, epoch),
        index=shard,
        count=SHARD_COUNT,
    )

    return full_committee[:TARGET_PERSISTENT_COMMITTEE_SIZE]
```

#### `get_persistent_committee`

```python
def get_persistent_committee(state: BeaconState, shard: Shard, epoch: Epoch) -> Sequence[ValidatorIndex]:
    earlier_committee = get_period_committee(state, compute_period_start_epoch(epoch, lookback=2), shard)
    later_committee = get_period_committee(state, compute_period_start_epoch(epoch, lookback=1), shard)

    # Take not-yet-cycled-out validators from earlier committee and already-cycled-in validators from
    # later committee; return a sorted list of the union of the two, deduplicated
    return sorted(set(
        [i for i in earlier_committee if epoch % EPOCHS_PER_SHARD_PERIOD < i % EPOCHS_PER_SHARD_PERIOD]
        + [i for i in later_committee if epoch % EPOCHS_PER_SHARD_PERIOD >= i % EPOCHS_PER_SHARD_PERIOD]
    ))
```

#### `get_shard_proposer_index`

```python
def get_shard_proposer_index(state: BeaconState, shard: Shard, slot: ShardSlot) -> ValidatorIndex:
    epoch = get_current_epoch(state)
    persistent_committee = list(get_persistent_committee(state, shard, epoch))
    active_indices = [i for i in persistent_committee if is_active_validator(state.validators[i], epoch)]
    assert len(active_indices) > 0

    MAX_RANDOM_BYTE = 2**8 - 1
    seed = hash(get_seed(state, epoch) + int_to_bytes(shard, length=8) + int_to_bytes(slot, length=8))
    i = 0
    while True:
        candidate_index = active_indices[(slot + i) % len(active_indices)]
        random_byte = hash(seed + int_to_bytes(i // 32, length=8))[i % 32]
        effective_balance = state.validators[candidate_index].effective_balance
        if effective_balance * MAX_RANDOM_BYTE >= MAX_EFFECTIVE_BALANCE * random_byte:
            return ValidatorIndex(candidate_index)
        i += 1
```

#### `get_default_shard_state`

```python
def get_default_shard_state(beacon_state: BeaconState, shard: Shard) -> ShardState:
    earlier_committee = get_period_committee(
        beacon_state,
        Epoch(PHASE_1_FORK_EPOCH - EPOCHS_PER_SHARD_PERIOD * 2),
        shard,
    )
    later_committee = get_period_committee(
        beacon_state,
        Epoch(PHASE_1_FORK_EPOCH - EPOCHS_PER_SHARD_PERIOD),
        shard,
    )
    return ShardState(
        basefee=1,
        shard=shard,
        slot=ShardSlot(PHASE_1_FORK_EPOCH * SHARD_SLOTS_PER_EPOCH),
        earlier_committee_rewards=[REWARD_COEFFICIENT_BASE for _ in range(len(earlier_committee))],
        later_committee_rewards=[REWARD_COEFFICIENT_BASE for _ in range(len(later_committee))],
        earlier_committee_fees=[Gwei(0) for _ in range(len(earlier_committee))],
        later_committee_fees=[Gwei(0) for _ in range(len(later_committee))],
    )
```

#### `get_shard_base_reward`

```python
def get_shard_base_reward(beacon_state: BeaconState) -> Gwei:
    total_balance_root = integer_squareroot(get_total_active_balance(beacon_state))
    return Gwei(REWARD_COEFFICIENT_BASE * BASE_REWARD_FACTOR // total_balance_root // BASE_REWARDS_PER_EPOCH)
```

### State mutators

#### `add_reward`

```python
def add_reward(state: ShardState, beacon_state: BeaconState, index: ValidatorIndex, delta: Gwei) -> None:
    epoch = compute_epoch_of_shard_slot(state.slot)
    earlier_committee = get_period_committee(beacon_state, compute_period_start_epoch(epoch, lookback=2), state.shard)
    later_committee = get_period_committee(beacon_state, compute_period_start_epoch(epoch, lookback=1), state.shard)
    if index in earlier_committee:
        state.earlier_committee_rewards[earlier_committee.index(index)] += delta
    elif index in later_committee:
        state.later_committee_rewards[later_committee.index(index)] += delta
```

#### `add_fee`

```python
def add_fee(state: ShardState, beacon_state: BeaconState, index: ValidatorIndex, delta: Gwei) -> None:
    epoch = compute_epoch_of_shard_slot(state.slot)
    earlier_committee = get_period_committee(beacon_state, compute_period_start_epoch(epoch, lookback=2), state.shard)
    later_committee = get_period_committee(beacon_state, compute_period_start_epoch(epoch, lookback=1), state.shard)
    if index in earlier_committee:
        state.earlier_committee_fees[earlier_committee.index(index)] += delta
    elif index in later_committee:
        state.later_committee_fees[later_committee.index(index)] += delta
```

## Shard state transition function

The post-state corresponding to a pre-state `state`, a beacon state `beacon_state`, and a block `block` is defined as `shard_state_transition(state, beacon_state, block)`. State transitions that trigger an unhandled exception (e.g. a failed `assert` or an out-of-range list access) are considered invalid.

```python
def shard_state_transition(state: ShardState,
                           beacon_state: BeaconState,
                           block: ShardBlock,
                           validate_state_root: bool=False) -> ShardState:
    # Process slots (including those with no blocks) since block
    process_shard_slots(state, beacon_state, block.slot)
    # Process block
    process_shard_block(state, beacon_state, block)
    # Validate state root (`validate_state_root == True` in production)
    if validate_state_root:
        assert block.state_root == hash_tree_root(state)
    # Return post-state
    return state
```

```python
def process_shard_slots(state: ShardState, beacon_state: BeaconState, slot: ShardSlot) -> None:
    assert state.slot <= slot
    while state.slot < slot:
        process_shard_slot(state)
        # Process period on the start slot of the next period
        if (state.slot + 1) % (SHARD_SLOTS_PER_EPOCH * EPOCHS_PER_SHARD_PERIOD) == 0:
            process_shard_period(state)
        state.slot += ShardSlot(1)
```

```python
def process_shard_slot(state: ShardState, beacon_state: BeaconState, slot: ShardSlot) -> None:
    # Cache state root
    if state.latest_block_header.state_root == Hash():
        state.latest_block_header.state_root = hash_tree_root(state)
    # Save state roots in history accumulator
    depth = 0
    state_root = hash_tree_root(state)
    while state.slot % 2**depth == 0 and depth < HISTORY_ACCUMULATOR_VECTOR:
        state.history_accumulator[depth] = state_root
        depth += 1
```

### Period processing

```python
def process_shard_period(state: ShardState, beacon_state: BeaconState) -> None:
    epoch = compute_epoch_of_shard_slot(state.slot)
    earlier_committee = get_period_committee(
        beacon_state,
        compute_period_start_epoch(epoch, lookback=2),
        state.shard,
    )
    later_committee = get_period_committee(
        beacon_state,
        compute_period_start_epoch(epoch, lookback=1),
        state.shard,
    )

    state.receipt_root = hash_tree_root(List[ShardReceiptDelta, TARGET_PERSISTENT_COMMITTEE_SIZE]([
        ShardReceiptDelta(validator_index, state.earlier_committee_rewards[i], state.earlier_committee_fees[i])
        for i, validator_index in enumerate(earlier_committee)
    ]))
    state.earlier_committee_rewards = state.later_committee_rewards
    state.earlier_committee_fees = state.later_committee_fees
    state.later_committee_rewards = [REWARD_COEFFICIENT_BASE for _ in range(len(later_committee))]
    state.later_committee_fees = [Gwei(0) for _ in range(len(later_committee))]
```

### Block processing

```python
def process_shard_block(state: ShardState, beacon_state: BeaconState, block: ShardBlock) -> None:
    process_shard_block_header(state, beacon_state, block)
    process_shard_attestations(state, beacon_state, block
    process_shard_block_data_fees(state, beacon_state, block)
```

#### Block header

```python
def process_shard_block_header(state: ShardState, beacon_state: BeaconState, block: ShardBlock) -> None:
    # Verify that the slots match
    assert block.slot == state.slot
    # Verify that the parent matches
    if block.parent_root != Hash():
        assert block.parent_root == signing_root(state.latest_block_header)
    # Save current block as the new latest block
    state.latest_block_header = ShardBlockHeader(
        slot=block.slot,
        beacon_chain_root=block.beacon_chain_root,
        parent_root=block.parent_root,
        # `state_root` is zeroed and overwritten in the next `process_shard_slot` call
        aggregation_bits=block.aggregation_bits,
        total_bytes=block.total_bytes,
        body_root=hash_tree_root(block.body),
        # `signatures` is zeroed
    )
    # Verify proposer signature
    proposer_index = get_shard_proposer_index(beacon_state, state.shard, block.slot)
    pubkey = beacon_state.validators[proposer_index].pubkey
    domain = get_domain(beacon_state, DOMAIN_SHARD_PROPOSER, compute_epoch_of_shard_slot(block.slot))
    assert bls_verify(pubkey, signing_root(block), block.signatures.proposer, domain)
    # Verify total bytes count
    state.total_bytes += len(block.body)
    assert block.total_bytes == state.total_bytes
```

#### Attestations

```python
def process_shard_attestations(state: ShardState, beacon_state: BeaconState, block: ShardBlock) -> None:
    persistent_committee = get_persistent_committee(beacon_state, state.shard, block.slot)
    pubkeys = []
    attestation_count = 0
    base_reward = get_shard_base_reward(beacon_state)
    for i, validator_index in enumerate(persistent_committee):
        if block.aggregation_bits[i]:
            pubkeys.append(beacon_state.validators[validator_index].pubkey)
            add_reward(state, beacon_state, validator_index, base_reward)
            attestation_count += 1
    for i in range(len(persistent_committee), TARGET_PERSISTENT_COMMITTEE_SIZE):
        assert block.aggregation_bits[i] is False or block.aggregation_bits[i] == 0  # TODO: Fix Bitvector
    # Verify aggregate signature
    domain = get_domain(beacon_state, DOMAIN_SHARD_ATTESTER, compute_epoch_of_shard_slot(block.slot))
    assert bls_verify(bls_aggregate_pubkeys(pubkeys), block.parent_root, block.signatures.attesters, domain)
    # Proposer micro-rewards
    add_reward(state, beacon_state, proposer_index, attestation_count * get_shard_base_reward(beacon_state) // PROPOSER_REWARD_QUOTIENT)
```

#### Block data fees

```python
def process_shard_block_data_fees(state: ShardState, beacon_state: BeaconState, block: ShardBlock) -> None:
    base_reward = get_shard_base_reward(beacon_state)
    add_fee(state, beacon_state, proposer_index, state.basefee * len(block.body) // SHARD_BLOCK_SIZE_LIMIT)
    QUOTIENT = SHARD_BLOCK_SIZE_LIMIT * BASEFEE_ADJUSTMENT_FACTOR
    if len(block.body) > SHARD_BLOCK_SIZE_TARGET:
        state.basefee += Gwei(max(1, state.basefee * (len(block.body) - SHARD_BLOCK_SIZE_TARGET) // QUOTIENT))
    elif len(block.body) < SHARD_BLOCK_SIZE_TARGET:
        state.basefee -= Gwei(max(1, state.basefee * (len(block.body) - SHARD_BLOCK_SIZE_TARGET) // QUOTIENT))
    state.basefee = Gwei(max(1, min( EFFECTIVE_BALANCE_INCREMENT // EPOCHS_PER_SHARD_PERIOD // SHARD_SLOTS_PER_EPOCH,
        state.basefee,
    )))
```

## Object validity

### Shard block validation: preliminary

Accept a shard block `block` only if all of the following are correct:

* Either `block.parent_root == Hash()` or a block `parent` such that `signing_root(parent) == block.parent_root` has already been accepted.
* `block.beacon_chain_root == get_block_root(head_beacon_state, compute_epoch_of_shard_slot(parent.slot))` where `head_beacon_state` is the current beacon chain head state. Alternatively phrased, a beacon chain block `beacon_ref` such that `signing_root(beacon_ref) == block.beacon_chain_root` has already been accepted and is part of the canonical chain, and no block with slot `beacon_ref.slot < slot <= compute_start_slot_of_epoch(compute_epoch_of_shard_slot(parent.slot))` is part of the canonical chain.
* Let `beacon_state` be the state where `beacon_ref.state_root == hash_tree_root(beacon_state)`. Let `prev_state` be the post-state of the `parent` if the `parent` exists, otherwise let it be `get_default_shard_state(beacon_state, shard)` (defined below). `block.state_root` must equal the `hash_tree_root` of the state after applying `shard_state_transition(prev_state, beacon_state, block)`.

Note that these acceptance conditions depend on the canonical beacon chain; when the canonical beacon chain reorganizes, the eligibility of shard blocks should be re-evaluated.

### Beacon attestations

Let:

- `pre_state` be the `ShardState` before processing any blocks
- `shard_blocks_or_state_roots` be the `Union[ShardBlock, Hash]` list such that `shard_blocks[slot]` is the canonical `ShardBlock` for shard `pre_state.shard` at slot `slot` if a block exists, or the post-state-root of processing state up to and including that slot if a block does not exist.
- `beacon_state` be the canonical `BeaconState`
- `valid_attestations` be the set of valid `Attestation` objects, recursively defined
- `candidate` be a candidate `Attestation` which is valid under Phase 0 rules, and for which validity is to be determined under Phase 1 rules by running `is_valid_beacon_attestation`

```python
def is_valid_beacon_attestation(pre_state: ShardState,
                                shard_blocks_or_state_roots: Sequence[Union[ShardBlock, Hash]],
                                beacon_state: BeaconState,
                                valid_attestations: Set[Attestation],
                                candidate: Attestation) -> bool:
    # Check if attestation is already determined valid
    for attestation in valid_attestations:
        if candidate == attestation:
            return True

    # Check previous attestation
    if candidate.data.previous_crosslink.epoch <= PHASE_1_FORK_EPOCH:
        assert candidate.data.previous_crosslink.data_root == Hash()
    else:
        previous_attestation = next(
            (attestation for attestation in valid_attestations
             if attestation.data.crosslink.data_root == candidate.data.previous_crosslink.data_root),
            None,
        )
        assert previous_attestation is not None
        assert candidate.data.previous_attestation.epoch < compute_epoch_of_slot(candidate.data.slot)

    # Check crosslink data root
    start_epoch = beacon_state.crosslinks[pre_state.shard].epoch
    end_epoch = min(compute_epoch_of_slot(candidate.data.slot) - CROSSLINK_LOOKBACK,
                    start_epoch + MAX_EPOCHS_PER_CROSSLINK)
    blocks = []
    for slot in range(start_epoch * SLOTS_PER_EPOCH, end_epoch * SLOTS_PER_EPOCH):
        if isinstance(shard_blocks_or_state_roots[slot], ShardBlock):
            blocks.append(shard_blocks_or_state_roots[slot])
        else:
            blocks.append(ShardBlock(
                slot=slot,
                state_root=shard_blocks_or_state_roots[slot],
                total_bytes=pre_state.total_bytes,
            ))
    assert candidate.data.crosslink.data_root == compute_crosslink_data_root(blocks)

    return True
```

## Shard fork choice rule

The fork choice rule for any shard is LMD GHOST using the shard attestations of the persistent committee and the beacon chain attestations of the crosslink committee currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (i.e. `state.crosslinks[shard].shard_block_root`). Only blocks whose `beacon_chain_root` is the block in the main beacon chain at the specified `slot` should be considered. (If the beacon chain skips a slot, then the block at that slot is considered to be the block in the beacon chain at the highest slot lower than that slot.)
