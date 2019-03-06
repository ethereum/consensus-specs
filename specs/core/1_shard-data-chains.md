# Ethereum 2.0 Phase 1 -- Shard Data Chains

**NOTICE**: This document is a work-in-progress for researchers and implementers. It reflects recent spec changes and takes precedence over the [Python proof-of-concept implementation](https://github.com/ethereum/beacon_chain).

At the current stage, Phase 1, while fundamentally feature-complete, is still subject to change. Development teams with spare resources may consider starting on the "Shard chains and crosslink data" section; at least basic properties, such as the fact that a shard block can get created every slot and is dependent on both a parent block in the same shard and a beacon chain block at or before that same slot, are unlikely to change, though details are likely to undergo similar kinds of changes to what Phase 0 has undergone since the start of the year.

## Table of contents

<!-- TOC -->

- [Ethereum 2.0 Phase 1 -- Shard Data Chains](#ethereum-20-phase-1----shard-data-chains)
    - [Table of contents](#table-of-contents)
        - [Introduction](#introduction)
        - [Terminology](#terminology)
        - [Constants](#constants)
            - [Misc](#misc)
            - [Time parameters](#time-parameters)
            - [Max operations per block](#max-operations-per-block)
            - [Signature domains](#signature-domains)
    - [Shard chains and crosslink data](#shard-chains-and-crosslink-data)
      - [Helper functions](#helper-functions)
            - [`get_split_offset`](#get_split_offset)
            - [`get_shuffled_committee`](#get_shuffled_committee)
            - [`get_persistent_committee`](#get_persistent_committee)
            - [`get_shard_proposer_index`](#get_shard_proposer_index)
      - [Data Structures](#data-structures)
        - [Shard chain blocks](#shard-chain-blocks)
      - [Shard block processing](#shard-block-processing)
        - [Verifying shard block data](#verifying-shard-block-data)
        - [Verifying a crosslink](#verifying-a-crosslink)
        - [Shard block fork choice rule](#shard-block-fork-choice-rule)
    - [Updates to the beacon chain](#updates-to-the-beacon-chain)
      - [Data structures](#data-structures)
        - [`Validator`](#validator)
        - [`BeaconBlockBody`](#beaconblockbody)
        - [`BranchChallenge`](#branchchallenge)
        - [`BranchResponse`](#branchresponse)
        - [`BranchChallengeRecord`](#branchchallengerecord)
        - [`SubkeyReveal`](#subkeyreveal)
    - [Helpers](#helpers)
        - [`get_attestation_data_merkle_depth`](#get_attestation_data_merkle_depth)
        - [`epoch_to_custody_period`](#epoch_to_custody_period)
        - [`slot_to_custody_period`](#slot_to_custody_period)
        - [`get_current_custody_period`](#get_current_custody_period)
        - [`verify_custody_subkey_reveal`](#verify_custody_subkey_reveal)
        - [`prepare_validator_for_withdrawal`](#prepare_validator_for_withdrawal)
        - [`penalize_validator`](#penalize_validator)
      - [Per-slot processing](#per-slot-processing)
        - [Operations](#operations)
            - [Branch challenges](#branch-challenges)
            - [Branch responses](#branch-responses)
            - [Subkey reveals](#subkey-reveals)
      - [Per-epoch processing](#per-epoch-processing)
      - [One-time phase 1 initiation transition](#one-time-phase-1-initiation-transition)

<!-- /TOC -->

### Introduction

This document represents the specification for Phase 1 of Ethereum 2.0 -- Shard Data Chains. Phase 1 depends on the implementation of [Phase 0 -- The Beacon Chain](0_beacon-chain.md).

Ethereum 2.0 consists of a central beacon chain along with `SHARD_COUNT` shard chains. Phase 1 is primarily concerned with the construction, validity, and consensus on the _data_ of these shard chains. Phase 1 does not specify shard chain state execution or account balances. This is left for future phases.

### Terminology

### Constants

Phase 1 depends upon all of the constants defined in [Phase 0](0_beacon-chain.md#constants) in addition to the following:

#### Misc

| Name                          | Value            | Unit   |
|-------------------------------|------------------|--------|
| `SHARD_CHUNK_SIZE`            | 2**5 (= 32)      | bytes  |
| `SHARD_BLOCK_SIZE`            | 2**14 (= 16,384) | bytes  |
| `MINOR_REWARD_QUOTIENT`       | 2**8 (= 256)     |        |
| `MAX_POC_RESPONSE_DEPTH`      | 5                |        |
| `ZERO_PUBKEY`                 | int_to_bytes48(0)|        |
| `VALIDATOR_NULL`              | 2**64 - 1        |        |

#### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `CROSSLINK_LOOKBACK`          | 2**5 (= 32)      | slots  | 3.2 minutes   |
| `MAX_BRANCH_CHALLENGE_DELAY`  | 2**11 (= 2,048)  | epochs | 9 days        |
| `CUSTODY_PERIOD_LENGTH`       | 2**11 (= 2,048)  | epochs | 9 days        |
| `PERSISTENT_COMMITTEE_PERIOD` | 2**11 (= 2,048)  | epochs | 9 days        |
| `CHALLENGE_RESPONSE_DEADLINE` | 2**14 (= 16,384) | epochs | 73 days       |

#### Max operations per block

| Name                                               | Value         |
|----------------------------------------------------|---------------|
| `MAX_BRANCH_CHALLENGES`                            | 2**2 (= 4)    |
| `MAX_BRANCH_RESPONSES`                             | 2**4 (= 16)   |
| `MAX_EARLY_SUBKEY_REVEALS`                         | 2**4 (= 16)   |
| `MAX_INTERACTIVE_CUSTODY_CHALLENGE_INITIATIONS`    | 2             |
| `MAX_INTERACTIVE_CUSTODY_CHALLENGE_RESPONSES`      | 16            |
| `MAX_INTERACTIVE_CUSTODY_CHALLENGE_CONTINUTATIONS` | 16            |

#### Signature domains

| Name                         | Value           |
|------------------------------|-----------------|
| `DOMAIN_SHARD_PROPOSER`      | 129             |
| `DOMAIN_SHARD_ATTESTER`      | 130             |
| `DOMAIN_CUSTODY_SUBKEY`      | 131             |
| `DOMAIN_CUSTODY_INTERACTIVE` | 132             |

# Shard chains and crosslink data

## Helper functions

#### `get_split_offset`

````python
def get_split_offset(list_size: int, chunks: int, index: int) -> int:
  """
  Returns a value such that for a list L, chunk count k and index i,
  split(L, k)[i] == L[get_split_offset(len(L), k, i): get_split_offset(len(L), k+1, i)]
  """
  return (len(list_size) * index) // chunks
````

#### `get_shuffled_committee`

```python
def get_shuffled_committee(state: BeaconState,
                           shard: Shard,
                           committee_start_epoch: Epoch) -> List[ValidatorIndex]:
    """
    Return shuffled committee.
    """
    validator_indices = get_active_validator_indices(state.validators, committee_start_epoch)
    seed = generate_seed(state, committee_start_epoch)
    start_offset = get_split_offset(len(validator_indices), SHARD_COUNT, shard)
    end_offset = get_split_offset(len(validator_indices), SHARD_COUNT, shard + 1)
    return [
        validator_indices[get_permuted_index(i, len(validator_indices), seed)]
        for i in range(start_offset, end_offset)
    ]
```

#### `get_persistent_committee`

```python
def get_persistent_committee(state: BeaconState,
                             shard: Shard,
                             epoch: Epoch) -> List[ValidatorIndex]:
    """
    Return the persistent committee for the given ``shard`` at the given ``epoch``.
    """
    earlier_committee_start_epoch = epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD * 2
    earlier_committee = get_shuffled_committee(state, shard, earlier_committee_start_epoch)

    later_committee_start_epoch = epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD
    later_committee = get_shuffled_committee(state, shard, later_committee_start_epoch)

    def get_switchover_epoch(index):
        return (
            bytes_to_int(hash(earlier_seed + bytes3(index))[0:8]) %
            PERSISTENT_COMMITTEE_PERIOD
        )

    # Take not-yet-cycled-out validators from earlier committee and already-cycled-in validators from
    # later committee; return a sorted list of the union of the two, deduplicated
    return sorted(list(set(
        [i for i in earlier_committee if epoch % PERSISTENT_COMMITTEE_PERIOD < get_switchover_epoch(i)] +
        [i for i in later_committee if epoch % PERSISTENT_COMMITTEE_PERIOD >= get_switchover_epoch(i)]
    )))
```
#### `get_shard_proposer_index`

```python
def get_shard_proposer_index(state: BeaconState,
                             shard: Shard,
                             slot: Slot) -> ValidatorIndex:
    seed = hash(
        state.current_shuffling_seed +
        int_to_bytes8(shard) +
        int_to_bytes8(slot)
    )
    persistent_committee = get_persistent_committee(state, shard, slot_to_epoch(slot))
    # Default proposer
    index = bytes_to_int(seed[0:8]) % len(persistent_committee)
    # If default proposer exits, try the other proposers in order; if all are exited
    # return None (ie. no block can be proposed)
    validators_to_try = persistent_committee[index:] + persistent_committee[:index]
    for index in validators_to_try:
        if is_active_validator(state.validators[index], get_current_epoch(state)):
            return index
    return None
```

## Data Structures

### Shard chain blocks

A `ShardBlock` object has the following fields:

```python
{
    # Slot number
    'slot': 'uint64',
    # What shard is it on
    'shard_id': 'uint64',
    # Parent block's root
    'parent_root': 'bytes32',
    # Beacon chain block
    'beacon_chain_ref': 'bytes32',
    # Merkle root of data
    'data_root': 'bytes32'
    # State root (placeholder for now)
    'state_root': 'bytes32',
    # Block signature
    'signature': 'bytes96',
    # Attestation
    'participation_bitfield': 'bytes',
    'aggregate_signature': 'bytes96',
}
```

## Shard block processing

For a `shard_block` on a shard to be processed by a node, the following conditions must be met:

* The `ShardBlock` pointed to by `shard_block.parent_root` has already been processed and accepted
* The signature for the block from the _proposer_ (see below for definition) of that block is included along with the block in the network message object

To validate a block header on shard `shard_block.shard_id`, compute as follows:

* Verify that `shard_block.beacon_chain_ref` is the hash of a block in the (canonical) beacon chain with slot less than or equal to `slot`.
* Verify that `shard_block.beacon_chain_ref` is equal to or a descendant of the `shard_block.beacon_chain_ref` specified in the `ShardBlock` pointed to by `shard_block.parent_root`.
* Let `state` be the state of the beacon chain block referred to by `shard_block.beacon_chain_ref`.
* Let `persistent_committee = get_persistent_committee(state, shard_block.shard_id, slot_to_epoch(shard_block.slot))`.
* Assert `verify_bitfield(shard_block.participation_bitfield, len(persistent_committee))`
* For every `i in range(len(persistent_committee))` where `is_active_validator(state.validators[persistent_committee[i]], get_current_epoch(state))` returns `False`, verify that `get_bitfield_bit(shard_block.participation_bitfield, i) == 0`
* Let `proposer_index = get_shard_proposer_index(state, shard_block.shard_id, shard_block.slot)`.
* Verify that `proposer_index` is not `None`.
* Let `msg` be the `shard_block` but with `shard_block.signature` set to `[0, 0]`.
* Verify that `bls_verify(pubkey=validators[proposer_index].pubkey, message_hash=hash(msg), signature=shard_block.signature, domain=get_domain(state, slot_to_epoch(shard_block.slot), DOMAIN_SHARD_PROPOSER))` passes.
* Let `group_public_key = bls_aggregate_pubkeys([state.validators[index].pubkey for i, index in enumerate(persistent_committee) if get_bitfield_bit(shard_block.participation_bitfield, i) is True])`.
* Verify that `bls_verify(pubkey=group_public_key, message_hash=shard_block.parent_root, sig=shard_block.aggregate_signature, domain=get_domain(state, slot_to_epoch(shard_block.slot), DOMAIN_SHARD_ATTESTER))` passes.

### Verifying shard block data

At network layer, we expect a shard block header to be broadcast along with its `block_body`.

* Verify that `len(block_body) == SHARD_BLOCK_SIZE`
* Verify that `merkle_root(block_body)` equals the `data_root` in the header.

### Verifying a crosslink

A node should sign a crosslink only if the following conditions hold. **If a node has the capability to perform the required level of verification, it should NOT follow chains on which a crosslink for which these conditions do NOT hold has been included, or a sufficient number of signatures have been included that during the next state recalculation, a crosslink will be registered.**

First, the conditions must recursively apply to the crosslink referenced in `last_crosslink_root` for the same shard (unless `last_crosslink_root` equals zero, in which case we are at the genesis).

Second, we verify the `shard_chain_commitment`.
* Let `start_slot = state.latest_crosslinks[shard].epoch * SLOTS_PER_EPOCH + SLOTS_PER_EPOCH - CROSSLINK_LOOKBACK`.
* Let `end_slot = attestation.data.slot - attestation.data.slot % SLOTS_PER_EPOCH - CROSSLINK_LOOKBACK`.
* Let `length = end_slot - start_slot`, `headers[0] .... headers[length-1]` be the serialized block headers in the canonical shard chain from the verifer's point of view (note that this implies that `headers` and `bodies` have been checked for validity).
* Let `bodies[0] ... bodies[length-1]` be the bodies of the blocks.
* Note: If there is a missing slot, then the header and body are the same as that of the block at the most recent slot that has a block.

We define two helpers:

```python
def pad_to_power_of_2(values: List[bytes]) -> List[bytes]:
    zero_shard_block = b'\x00' * SHARD_BLOCK_SIZE
    while not is_power_of_two(len(values)):
        values = values + [zero_shard_block]
    return values
```

```python
def merkle_root_of_bytes(data: bytes) -> bytes:
    return merkle_root([data[i:i + 32] for i in range(0, len(data), 32)])
```

We define the function for computing the commitment as follows:

```python
def compute_commitment(headers: List[ShardBlock], bodies: List[bytes]) -> Bytes32:
    return hash(
        merkle_root(
            pad_to_power_of_2([
                merkle_root_of_bytes(zpad(serialize(h), SHARD_BLOCK_SIZE)) for h in headers
            ])
        ) +
        merkle_root(
            pad_to_power_of_2([
                merkle_root_of_bytes(h) for h in bodies
            ])
        )
    )
```

The `shard_chain_commitment` is only valid if it equals `compute_commitment(headers, bodies)`.


### Shard block fork choice rule

The fork choice rule for any shard is LMD GHOST using the shard chain attestations of the persistent committee and the beacon chain attestations of the crosslink committee currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (ie. `state.crosslinks[shard].shard_block_root`). Only blocks whose `beacon_chain_ref` is the block in the main beacon chain at the specified `slot` should be considered (if the beacon chain skips a slot, then the block at that slot is considered to be the block in the beacon chain at the highest slot lower than a slot).

# Updates to the beacon chain

## Data structures

### `Validator`

Add member values to the end of the `Validator` object:

```python
    'next_subkey_to_reveal': 'uint64',
    'reveal_max_periods_late': 'uint64',
```

And the initializers:

```python
    'next_subkey_to_reveal': get_current_custody_period(state),
    'reveal_max_periods_late': 0,
```

### `BeaconBlockBody`

Add member values to the `BeaconBlockBody` structure:

```python
    'branch_challenges': [BranchChallenge],
    'branch_responses': [BranchResponse],
    'subkey_reveals': [SubkeyReveal],
    'interactive_custody_challenge_initiations': [InteractiveCustodyChallengeInitiation],
    'interactive_custody_challenge_responses': [InteractiveCustodyChallengeResponse],
    'interactive_custody_challenge_continuations': [InteractiveCustodyChallengeContinuation],

```

And initialize to the following:

```python
    'branch_challenges': [],
    'branch_responses': [],
    'subkey_reveals': [],
```

### `BeaconState`

Add member values to the `BeaconState` structure:

```python
    'branch_challenge_records': [BranchChallengeRecord],
    'next_branch_challenge_id': 'uint64',
    'custody_challenge_records': [InteractiveCustodyChallengeRecord],
    'next_custody_challenge_id': 'uint64',
```

### `BranchChallenge`

Define a `BranchChallenge` as follows:

```python
{
    'responder_index': 'uint64',
    'data_index': 'uint64',
    'attestation': SlashableAttestation,
}
```

### `BranchResponse`

Define a `BranchResponse` as follows:

```python
{
    'challenge_id': 'uint64',
    'responding_to_custody_challenge': 'bool',
    'data': 'bytes32',
    'branch': ['bytes32'],
}
```

### `BranchChallengeRecord`

Define a `BranchChallengeRecord` as follows:

```python
{
    'challenge_id': 'uint64',
    'challenger_index': 'uint64',
    'responder_index': 'uint64',
    'root': 'bytes32',
    'depth': 'uint64',
    'deadline': 'uint64',
    'data_index': 'uint64',
}
```

### `InteractiveCustodyChallengeRecord`

```python
{
    'challenge_id': 'uint64',
    'challenger_index': 'uint64',
    'responder_index': 'uint64',
    # Initial data root
    'data_root': 'bytes32',
    # Initial custody bit
    'custody_bit': 'bool',
    # Responder subkey
    'responder_subkey': 'bytes96',
    # The hash in the PoC tree in the position that we are currently at
    'current_custody_tree_node': 'bytes32',
    # The position in the tree, in terms of depth and position offset
    'depth': 'uint64',
    'offset': 'uint64',
    # Max depth of the branch
    'max_depth': 'uint64',
    # Deadline to respond (as an epoch)
    'deadline': 'uint64',
}
```

### `InteractiveCustodyChallengeInitiation`

```python
{
    'attestation': SlashableAttestation,
    'responder_index': 'uint64',
    'challenger_index': 'uint64',
    'responder_subkey': 'bytes96',
    'signature': 'bytes96',
}
```

### `InteractiveCustodyChallengeResponse`

```python
{
    'challenge_id': 'uint64',
    'hashes': ['bytes32'],
    'signature': 'bytes96',
}
```

### `InteractiveCustodyChallengeContinuation`

```python
{
    'challenge_id': 'uint64',
    'sub_index': 'uint64',
    'new_custody_tree_node': 'bytes32',
    'proof': ['bytes32'],
    'signature': 'bytes96',
}
```

### `SubkeyReveal`

Define a `SubkeyReveal` as follows:

```python
{
    'validator_index': 'uint64',
    'period': 'uint64',
    'subkey': 'bytes96',
    'mask': 'bytes32',
    'revealer_index': 'uint64'
}
```

## Helpers

### `get_branch_challenge_record_by_id`

```python
def get_branch_challenge_record_by_id(state: BeaconState, id: int) -> BranchChallengeRecord:
    return [c for c in state.branch_challenges if c.challenge_id == id][0]
```

### `get_custody_challenge_record_by_id`

```python
def get_custody_challenge_record_by_id(state: BeaconState, id: int) -> BranchChallengeRecord:
    return [c for c in state.branch_challenges if c.challenge_id == id][0]
```

### `get_attestation_merkle_depth`

```python
def get_attestation_merkle_depth(attestation: Attestation) -> int:
    start_epoch = attestation.data.latest_crosslink.epoch
    end_epoch = slot_to_epoch(attestation.data.slot)
    chunks_per_slot = SHARD_BLOCK_SIZE // 32
    chunks = (end_epoch - start_epoch) * EPOCH_LENGTH * chunks_per_slot
    return log2(next_power_of_two(chunks))
```

### `epoch_to_custody_period`

```python
def epoch_to_custody_period(epoch: Epoch) -> int:
    return epoch // CUSTODY_PERIOD_LENGTH
```

### `slot_to_custody_period`

```python
def slot_to_custody_period(slot: Slot) -> int:
    return epoch_to_custody_period(slot_to_epoch(slot))
```

### `get_current_custody_period`

```python
def get_current_custody_period(state: BeaconState) -> int:
    return epoch_to_custody_period(get_current_epoch(state))
```

### `verify_custody_subkey_reveal`

```python
def verify_custody_subkey_reveal(pubkey: bytes48,
                                 subkey: bytes96,
                                 mask: bytes32,
                                 mask_pubkey: bytes48,
                                 period: int) -> bool:
    # Legitimate reveal: checking that the provided value actually is the subkey
    if mask == ZERO_HASH:
        pubkeys=[pubkey]
        message_hashes=[hash(int_to_bytes8(period))]
        
    # Punitive early reveal: checking that the provided value is a valid masked subkey
    # (masking done to prevent "stealing the reward" from a whistleblower by block proposers)
    # Secure under the aggregate extraction infeasibility assumption described on page 11-12
    # of https://crypto.stanford.edu/~dabo/pubs/papers/aggreg.pdf
    else:
        pubkeys=[pubkey, mask_pubkey]
        message_hashes=[hash(int_to_bytes8(period)), mask]
        
    return bls_multi_verify(
        pubkeys=pubkeys,
        message_hashes=message_hashes,
        signature=subkey,
        domain=get_domain(
            fork=state.fork,
            epoch=period * CUSTODY_PERIOD_LENGTH,
            domain_type=DOMAIN_CUSTODY_SUBKEY,
        )
    )
```

### `verify_signed_challenge_message`

```python
def verify_signed_challenge_message(message: Any, pubkey: bytes48) -> bool:
    return bls_verify(
        message_hash=signed_root(message, 'signature'),
        pubkey=pubkey,
        signature=message.signature,
        domain=get_domain(state, get_current_epoch(state), DOMAIN_CUSTODY_INTERACTIVE)
    )

```

### `penalize_validator`

Change the definition of `penalize_validator` as follows:

```python
def penalize_validator(state: BeaconState, index: ValidatorIndex, whistleblower_index=None:ValidatorIndex) -> None:
    """
    Penalize the validator of the given ``index``.
    Note that this function mutates ``state``.
    """
    exit_validator(state, index)
    validator = state.validator_registry[index]
    state.latest_penalized_balances[get_current_epoch(state) % LATEST_PENALIZED_EXIT_LENGTH] += get_effective_balance(state, index)
    
    block_proposer_index = get_beacon_proposer_index(state, state.slot)
    whistleblower_reward = get_effective_balance(state, index) // WHISTLEBLOWER_REWARD_QUOTIENT
    if whistleblower_index is None:
        state.validator_balances[block_proposer_index] += whistleblower_reward
    else:
        state.validator_balances[whistleblower_index] += (
            whistleblower_reward * INCLUDER_REWARD_QUOTIENT / (INCLUDER_REWARD_QUOTIENT + 1)
        )
        state.validator_balances[block_proposer_index] += whistleblower_reward / (INCLUDER_REWARD_QUOTIENT + 1)
    state.validator_balances[index] -= whistleblower_reward
    validator.penalized_epoch = get_current_epoch(state)
    validator.withdrawable_epoch = get_current_epoch(state) + LATEST_PENALIZED_EXIT_LENGTH
```

The only change is that this introduces the possibility of a penalization where the "whistleblower" that takes credit is NOT the block proposer.

## Per-slot processing

### Operations

Add the following operations to the per-slot processing, in order the given below and _after_ all other operations (specifically, right after exits).

#### Branch challenges

Verify that `len(block.body.branch_challenges) <= MAX_BRANCH_CHALLENGES`.

For each `challenge` in `block.body.branch_challenges`, run:

```python
def process_branch_challenge(challenge: BranchChallenge,
                             state: BeaconState):
    # Check that it's not too late to challenge
    assert slot_to_epoch(challenge.attestation.data.slot) >= get_current_epoch(state) - MAX_BRANCH_CHALLENGE_DELAY
    assert state.validator_registry[responder_index].exit_epoch >= get_current_epoch(state) - MAX_BRANCH_CHALLENGE_DELAY
    # Check the attestation is valid
    assert verify_slashable_attestation(state, challenge.attestation)
    # Check that the responder participated
    assert challenger.responder_index in challenge.attestation.validator_indices
    # Check the challenge is not a duplicate
    assert [
        c for c in state.branch_challenge_records if c.root == challenge.attestation.data.crosslink_data_root and
        c.data_index == challenge.data_index
    ] == []
    # Check validity of depth
    depth = get_attestation_merkle_depth(challenge.attestation)
    assert c.data_index < 2**depth
    # Add new challenge
    state.branch_challenge_records.append(BranchChallengeRecord(
        challenge_id=state.next_branch_challenge_id,
        challenger_index=get_beacon_proposer_index(state, state.slot),
        root=challenge.attestation.data.shard_chain_commitment,
        depth=depth,
        deadline=get_current_epoch(state) + CHALLENGE_RESPONSE_DEADLINE,
        data_index=challenge.data_index
    ))
    state.next_branch_challenge_id += 1
```

#### Branch responses

Verify that `len(block.body.branch_responses) <= MAX_BRANCH_RESPONSES`.

For each `response` in `block.body.branch_responses`, if `response.responding_to_custody_challenge == False`, run:

```python
def process_branch_exploration_response(response: BranchResponse,
                                        state: BeaconState):
    challenge = get_branch_challenge_record_by_id(response.challenge_id)
    assert verify_merkle_branch(
        leaf=response.data,
        branch=response.branch,
        depth=challenge.depth,
        index=challenge.data_index,
        root=challenge.root
    )
    # Must wait at least ENTRY_EXIT_DELAY before responding to a branch challenge
    assert get_current_epoch(state) >= challenge.inclusion_epoch + ENTRY_EXIT_DELAY
    state.branch_challenge_records.pop(challenge)
    # Reward the proposer
    proposer_index = get_beacon_proposer_index(state, state.slot)
    state.validator_balances[proposer_index] += base_reward(state, index) // MINOR_REWARD_QUOTIENT
```

If `response.responding_to_custody_challenge == True`, run:

```python
def process_branch_custody_response(response: BranchResponse,
                                    state: BeaconState):
    challenge = get_custody_challenge_record_by_id(response.challenge_id)
    responder = state.validator_registry[challenge.responder_index]
    # Verify we're not too late
    assert get_current_epoch(state) < responder.withdrawable_epoch
    # Verify the Merkle branch *of the data tree*
    assert verify_merkle_branch(
        leaf=response.data,
        branch=response.branch,
        depth=challenge.max_depth,
        index=challenge.offset,
        root=challenge.data_root
    )
    # Responder wins
    if hash(challenge.responder_subkey + response.data) == challenge.current_custody_tree_node:
        penalize_validator(state, challenge.challenger_index, challenge.responder_index)
    # Challenger wins
    else:
        penalize_validator(state, challenge.responder_index, challenge.challenger_index)
    state.custody_challenge_records.pop(challenge)
```

#### Subkey reveals

Verify that `len(block.body.early_subkey_reveals) <= MAX_EARLY_SUBKEY_REVEALS`.

For each `reveal` in `block.body.early_subkey_reveals`:

* Verify that `verify_custody_subkey_reveal(state.validator_registry[reveal.validator_index].pubkey, reveal.subkey, reveal.period, reveal.mask, state.validator_registry[reveal.revealer_index].pubkey)` returns `True`.
* Let `is_early_reveal = reveal.period > get_current_custody_period(state) or (reveal.period == get_current_custody_period(state) and state.validator_registry[reveal.validator_index].exit_epoch > get_current_epoch(state))` (ie. either the reveal is of a future period, or it's of the current period and the validator is still active)
* Verify that one of the following is true:
    * (i) `is_early_reveal` is `True`
    * (ii) `is_early_reveal` is `False` and `reveal.period == state.validator_registry[reveal.validator_index].next_subkey_to_reveal` (revealing a past subkey, or a current subkey for a validator that has exited) and `reveal.mask == ZERO_HASH`

In case (i):

* Verify that `state.validator_registry[reveal.validator_index].penalized_epoch > get_current_epoch(state).
* Run `penalize_validator(state, reveal.validator_index, reveal.revealer_index)`.
* Set `state.validator_balances[reveal.revealer_index] += base_reward(state, index) // MINOR_REWARD_QUOTIENT`

In case (ii):

* Determine the proposer `proposer_index = get_beacon_proposer_index(state, state.slot)` and set `state.validator_balances[proposer_index] += base_reward(state, index) // MINOR_REWARD_QUOTIENT`.
* Set `state.validator_registry[reveal.validator_index].next_subkey_to_reveal += 1`
* Set `state.validator_registry[reveal.validator_index].reveal_max_periods_late = max(state.validator_registry[reveal.validator_index].reveal_max_periods_late, get_current_period(state) - reveal.period)`.

#### Interactive custody challenge initiations

Verify that `len(block.body.interactive_custody_challenge_initiations) <= MAX_INTERACTIVE_CUSTODY_CHALLENGE_INITIATIONS`.

For each `initiation` in `block.body.interactive_custody_challenge_initiations`, use the following function to process it:

```python
def process_initiation(initiation: InteractiveCustodyChallengeInitiation,
                       state: BeaconState):
    challenger = state.validator_registry[initiation.challenger_index]
    responder = state.validator_registry[initiation.responder_index]
    # Verify the signature
    assert verify_signed_challenge_message(initiation, challenger.pubkey)
    # Verify the attestation
    assert verify_slashable_attestation(initiation.attestation, state)
    # Check that the responder actually participated in the attestation
    assert initiation.responder_index in attestation.validator_indices
    # Any validator can be a challenger or responder of max 1 challenge at a time
    for c in state.custody_challenge_records:
        assert c.challenger_index != initiation.challenger_index
        assert c.responder_index != initiation.responder_index
    # Can't challenge if you've been penalized
    assert challenger.penalized_epoch == FAR_FUTURE_EPOCH
    # Make sure the revealed subkey is valid
    assert verify_custody_subkey_reveal(
        pubkey=state.validator_registry[responder_index].pubkey,
        subkey=initiation.responder_subkey,
        period=slot_to_custody_period(attestation.data.slot)
    )
    # Verify that the attestation is still eligible for challenging
    min_challengeable_epoch = responder.exit_epoch - CUSTODY_PERIOD_LENGTH * (1 + responder.reveal_max_periods_late)
    assert min_challengeable_epoch <= slot_to_epoch(initiation.attestation.data.slot) 
    # Create a new challenge object
    state.branch_challenge_records.append(InteractiveCustodyChallengeRecord(
        challenge_id=state.next_branch_challenge_id,
        challenger_index=initiation.challenger_index,
        responder_index=initiation.responder_index,
        data_root=attestation.custody_commitment,
        custody_bit=get_bitfield_bit(attestation.custody_bitfield, attestation.validator_indices.index(responder_index)),
        responder_subkey=responder_subkey,
        current_custody_tree_node=ZERO_HASH,
        depth=0,
        offset=0,
        max_depth=get_attestation_data_merkle_depth(initiation.attestation.data),
        deadline=get_current_epoch(state) + CHALLENGE_RESPONSE_DEADLINE
    ))
    state.next_branch_challenge_id += 1
    # Responder can't withdraw yet!
    state.validator_registry[responder_index].withdrawable_epoch = FAR_FUTURE_EPOCH
```

#### Interactive custody challenge responses

A response provides 32 hashes that are under current known proof of custody tree node. Note that at the beginning the tree node is just one bit of the custody root, so we ask the responder to sign to commit to the top 5 levels of the tree and therefore the root hash; at all other stages in the game responses are self-verifying.

Verify that `len(block.body.interactive_custody_challenge_responses) <= MAX_INTERACTIVE_CUSTODY_CHALLENGE_RESPONSES`.

For each `response` in `block.body.interactive_custody_challenge_responses`, use the following function to process it:

```python
def process_response(response: InteractiveCustodyChallengeResponse,
                     state: State):
    challenge = get_custody_challenge_record_by_id(state, response.challenge_id)
    responder = state.validator_registry[challenge.responder_index]
    # Check that the right number of hashes was provided
    expected_depth = min(challenge.max_depth - challenge.depth, MAX_POC_RESPONSE_DEPTH)
    assert 2**expected_depth == len(response.hashes)
    # Must make some progress!
    assert expected_depth > 0
    # Check the hashes match the previously provided root
    root = merkle_root(response.hashes)
    # If this is the first response check the bit and the signature and set the root
    if challenge.depth == 0:
        assert get_bitfield_bit(root, 0) == challenge.custody_bit
        assert verify_signed_challenge_message(response, responder.pubkey)
        challenge.current_custody_tree_node = root
    # Otherwise just check the response against the root
    else:
        assert root == challenge_data.current_custody_tree_node
    # Update challenge data
    challenge.deadline=FAR_FUTURE_EPOCH
    responder.withdrawable_epoch = get_current_epoch(state) + MAX_POC_RESPONSE_DEPTH
```

#### Interactive custody challenge continuations

Once a response provides 32 hashes, the challenger has the right to choose any one of them that they feel is constructed incorrectly to continue the game. Note that eventually, the game will get to the point where the `new_custody_tree_node` is a leaf node.

Verify that `len(block.body.interactive_custody_challenge_continuations) <= MAX_INTERACTIVE_CUSTODY_CHALLENGE_CONTINUATIONS`.

For each `continuation` in `block.body.interactive_custody_challenge_continuations`, use the following function to process it:

```python
def process_continuation(continuation: InteractiveCustodyChallengeContinuation,
                         state: State):
    challenge = get_custody_challenge_record_by_id(state, continuation.challenge_id)
    challenger = state.validator_registry[challenge.challenger_index]
    responder = state.validator_registry[challenge.responder_index]
    expected_depth = min(challenge_data.max_depth - challenge_data.depth, MAX_POC_RESPONSE_DEPTH)
    # Verify we're not too late
    assert get_current_epoch(state) < responder.withdrawable_epoch
    # Verify the Merkle branch (the previous custody response provided the next level of hashes so the
    # challenger has the info to make any Merkle branch)
    assert verify_merkle_branch(
        leaf=new_custody_tree_node,
        branch=continuation.proof,
        depth=expected_depth,
        index=sub_index,
        root=challenge_data.current_custody_tree_node
    )
    # Verify signature
    assert verify_signed_challenge_message(continuation, challenger.pubkey)
    # Update the challenge data
    challenge.current_custody_tree_node = continuation.new_custody_tree_node
    challenge.depth += expected_depth
    challenge.deadline = get_current_epoch(state) + MAX_POC_RESPONSE_DEPTH
    responder.withdrawable_epoch = FAR_FUTURE_EPOCH
    challenge.offset = challenge_data.offset * 2**expected_depth + sub_index
```

## Per-epoch processing

Add the following loop immediately below the `process_ejections` loop:

```python
def process_challenge_absences(state: BeaconState) -> None:
    """
    Iterate through the challenge list
    and penalize validators with balance that did not answer challenges.
    """
    for c in state.branch_challenge_records:
        if get_current_epoch(state) > c.deadline:
            penalize_validator(state, c.responder_index, c.challenger_index)
    
    for c in state.custody_challenge_records:
        if get_current_epoch(state) > c.deadline:
            penalize_validator(state, c.responder_index, c.challenger_index)
        if get_current_epoch(state) > state.validator_registry[c.responder_index].withdrawable_epoch:
            penalize_validator(state, c.challenger_index, c.responder_index)
```

In `process_penalties_and_exits`, change the definition of `eligible` to the following (note that it is not a pure function because `state` is declared in the surrounding scope):

```python
def eligible(index):
    validator = state.validator_registry[index]
    # Cannot exit if there are still open branch challenges
    if [c for c in state.branch_challenge_records if c.responder_index == index] != []:
        return False
    # Cannot exit if you have not revealed all of your subkeys
    elif validator.next_subkey_to_reveal <= epoch_to_custody_period(validator.exit_epoch):
        return False
    # Cannot exit if you already have
    elif validator.withdrawable_epoch < FAR_FUTURE_EPOCH:
        return False
    # Return minimum time
    else:
        return current_epoch >= validator.exit_epoch + MIN_VALIDATOR_WITHDRAWAL_EPOCHS
```

## One-time phase 1 initiation transition

Run the following on the fork block after per-slot processing and before per-block and per-epoch processing.

For all `validator` in `ValidatorRegistry`, update it to the new format and fill the new member values with:

```python
    'next_subkey_to_reveal': get_current_custody_period(state),
    'reveal_max_periods_late': 0,
```

Update the `BeaconState` to the new format and fill the new member values with:

```python
    'branch_challenge_records': [],
    'next_branch_challenge_id': 0,
    'custody_challenge_records': [],
    'next_custody_challenge_id': 0,
```
