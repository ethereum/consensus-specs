# Ethereum 2.0 Phase 1 -- Shard Data Chains

###### tags: `spec`, `eth2.0`, `casper`, `sharding`

**NOTICE**: This document is a work-in-progress for researchers and implementers. It reflects recent spec changes and takes precedence over the [Python proof-of-concept implementation](https://github.com/ethereum/beacon_chain).

### Introduction

This document represents the specification for Phase 1 of Ethereum 2.0 -- Shard Data Chains. Phase 1 depends on the implementation of [Phase 0 -- The Beacon Chain](0_beacon-chain.md).

Ethereum 2.0 consists of a central beacon chain along with `SHARD_COUNT` shard chains. Phase 1 is primarily concerned with the construction, validity, and consensus on the _data_ of these shard chains. Phase 1 does not specify shard chain state execution or account balances. This is left for future phases.

### Terminology

### Constants

Phase 1 depends upon all of the constants defined in [Phase 0](0_beacon-chain.md#constants) in addition to the following:

| Constant                      | Value            | Unit   | Approximation |
|-------------------------------|------------------|--------|---------------|
| `SHARD_CHUNK_SIZE`            | 2**5 (= 32)      | bytes  |               |
| `SHARD_BLOCK_SIZE`            | 2**14 (= 16,384) | bytes  |               |
| `CROSSLINK_LOOKBACK`          | 2**5 (= 32)      | slots  |               |
| `PERSISTENT_COMMITTEE_PERIOD` | 2**11 (= 2,048)  | epochs | 9 days        |

### Flags, domains, etc.

| Constant               | Value           |
|------------------------|-----------------|
| `SHARD_PROPOSER_DOMAIN`| 129             |
| `SHARD_ATTESTER_DOMAIN`| 130             |

## Helper functions

#### get_split_offset

````python
def get_split_offset(list_size: int, chunks: int, index: int) -> int:
  """
  Returns a value such that for a list L, chunk count k and index i,
  split(L, k)[i] == L[get_split_offset(len(L), k, i): get_split_offset(len(L), k+1, i)]
  """
  return (len(list_size) * index) // chunks
````

#### get_shuffled_committee

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

#### get_persistent_committee

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
#### get_shard_proposer_index

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
* Verify that `bls_verify(pubkey=validators[proposer_index].pubkey, message_hash=hash(msg), signature=shard_block.signature, domain=get_domain(state, slot_to_epoch(shard_block.slot), SHARD_PROPOSER_DOMAIN))` passes.
* Let `group_public_key = bls_aggregate_pubkeys([state.validators[index].pubkey for i, index in enumerate(persistent_committee) if get_bitfield_bit(shard_block.participation_bitfield, i) is True])`.
* Verify that `bls_verify(pubkey=group_public_key, message_hash=shard_block.parent_root, sig=shard_block.aggregate_signature, domain=get_domain(state, slot_to_epoch(shard_block.slot), SHARD_ATTESTER_DOMAIN))` passes.

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

# Proof of custody interactive game

### Constants

| Constant                                   | Value            | Unit    | Approximation |
|--------------------------------------------|------------------|---------|---------------|
| `MAX_POC_RESPONSE_DEPTH`                   | 5                | layers  |               |
| `DOMAIN_CUSTODY_INTERACTIVE`               | 132              |         |               |
| `VALIDATOR_NULL`                           | 2**64 - 1        |         |               |
| `MAX_INTERACTIVE_CHALLENGE_INITIATIONS`    | 2                |         |               |
| `MAX_INTERACTIVE_CHALLENGE_RESPONSES`      | 16               |         |               |
| `MAX_INTERACTIVE_CHALLENGE_CONTINUTATIONS` | 16               |         |               |

### Data structures and verification

Add the following data structure to the `Validator` record:

```python
    interactive_custody_challenge_data: InteractiveCustodyChallengeData,
    now_challenging: 'uint64',
```

Where `InteractiveCustodyChallengeData` is defined as follows:

```python
{
    # Who initiated the challenge
    'challenger': 'uint64',
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

The initial value is `EMPTY_CHALLENGE_DATA = InteractiveCustodyChallengeData(challenger=VALIDATOR_NULL, data_root=ZERO_HASH, custody_bit=False, responder_subkey=EMPTY_SIGNATURE, current_custody_tree_node=ZERO_HASH, depth=0, offset=0, max_depth=0, deadline=0)`

We define an `InteractiveCustodyChallengeInitiation` as follows:

```python
{
    'attestation': SlashableAttestation,
    'responder_index': 'uint64',
    'challenger_index': 'uint64',
    'responder_subkey': 'bytes96',
    'signature': 'bytes96'
}
```

Here's the function for validating and processing an initiation:

```python
def process_initiation(initiation: InteractiveCustodyChallengeInitiation,
                       state: BeaconState):
    challenger = state.validator_registry[challenger_index]
    responder = state.validator_registry[responder_index]
    # Verify the signature                   
    assert bls_verify(
        message_hash=signed_root(initiation, 'signature'),
        pubkey=state.validator_registry[challenger_index].pubkey,
        signature=initiation.signature,
        domain=get_domain(state, get_current_epoch(state), DOMAIN_CUSTODY_INTERACTIVE)
    )
    # Check that the responder actually participated in the attestation
    assert responder_index in attestation.validator_indices
    # Can only be challenged by one challenger at a time
    assert responder.interactive_custody_challenge_data.challenger_index == VALIDATOR_NULL
    # Can only challenge one responder at a time
    assert challenger.now_challenging == VALIDATOR_NULL
    # Can't challenge if you've been penalized
    assert challenger.penalized_epoch == FAR_FUTURE_EPOCH
    # Make sure the revealed subkey is valid
    assert verify_custody_subkey_reveal(
        pubkey=state.validator_registry[responder_index].pubkey,
        subkey=responder_subkey,
        mask=ZERO_HASH,
        mask_pubkey=b'',
        period=slot_to_custody_period(attestation.data.slot)
    )
    # Set the challenge object
    responder.interactive_custody_challenge_data = InteractiveCustodyChallengeData(
        challenger=initiation.challenger_index,
        data_root=attestation.custody_commitment,
        custody_bit=get_bitfield_bit(attestation.custody_bitfield, attestation.validator_indices.index(responder_index)),
        responder_subkey=responder_subkey,
        current_custody_tree_node=ZERO_HASH,
        depth=0,
        offset=0,
        max_depth=get_merkle_depth(initiation.attestation),
        deadline=get_current_epoch(state) + CHALLENGE_RESPONSE_DEADLINE
    )
    # Responder can't withdraw yet!
    state.validator_registry[responder_index].withdrawable_epoch = FAR_FUTURE_EPOCH
    # Challenger can't challenge anyone else
    challenger.now_challenging = responder_index
```

We define an `InteractiveCustodyChallengeResponse` as follows:

```python
{
    'responder_index': 'uint64',
    'hashes': ['bytes32'],
    'signature': 'bytes96',
}
```

A response provides 32 hashes that are under current known proof of custody tree node. Note that at the beginning the tree node is just one bit of the custody root, so we ask the responder to sign to commit to the top 5 levels of the tree and therefore the root hash; at all other stages in the game responses are self-verifying.

Here's the function for verifying and processing a response:

```python
def process_response(response: InteractiveCustodyChallengeResponse,
                     state: State):
    responder = state.validator_registry[response.responder_index]
    challenge_data = responder.interactive_custody_challenge_data
    # Check that the right number of hashes was provided
    expected_depth = min(challenge_data.max_depth - challenge_data.depth, MAX_POC_RESPONSE_DEPTH)
    assert 2**expected_depth == len(response.hashes)
    # Must make some progress!
    assert expected_depth > 0
    # Check the hashes match the previously provided root
    root = merkle_root(response.hashes)
    # If this is the first response check the bit and the signature and set the root
    if challenge_data.depth == 0:
        assert get_bitfield_bit(root, 0) == challenge_data.custody_bit
        assert bls_verify(
            message_hash=signed_root(response, 'signature'),
            pubkey=responder.pubkey,
            signature=response.signature,
            domain=get_domain(state, get_current_epoch(state), DOMAIN_CUSTODY_INTERACTIVE)
        )
        challenge_data.current_custody_tree_node = root
    # Otherwise just check the response against the root
    else:
        assert root == challenge_data.current_custody_tree_node
    # Update challenge data
    challenge_data.deadline=FAR_FUTURE_EPOCH
    responder.withdrawable_epoch = get_current_epoch(state) + MAX_POC_RESPONSE_DEPTH
```

Once a response provides 32 hashes, the challenger has the right to choose any one of them that they feel is constructed incorrectly to continue the game. Note that eventually, the game will get to the point where the `new_custody_tree_node` is a leaf node. We define an `InteractiveCustodyChallengeContinuation` object as follows:

```python
{
    'challenger_index: 'uint64',
    'responder_index': 'uint64',
    'sub_index': 'uint64',
    'new_custody_tree_node': 'bytes32',
    'proof': ['bytes32'],
    'signature': 'bytes96'
}
```

Here's the function for verifying and processing a continuation challenge:

```python
def process_continuation(continuation: InteractiveCustodyChallengeContinuation,
                         state: State):
    responder = state.validator_registry[continuation.responder_index]
    challenge_data = responder.interactive_custody_challenge_data
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
    assert bls_verify(message_hash=signed_root(continutation, 'signature'),
                      pubkey=responder.pubkey,
                      signature=continutation.signature,
                      domain=get_domain(state, get_current_epoch(state), DOMAIN_CUSTODY_INTERACTIVE))
    # Update the challenge data
    challenge_data.current_custody_tree_node = continuation.new_custody_tree_node
    challenge_data.depth += expected_depth
    challenge_data.deadline = get_current_epoch(state) + MAX_POC_RESPONSE_DEPTH
    responder.withdrawable_epoch = FAR_FUTURE_EPOCH
    challenge_data.offset = challenger_data.offset * 2**expected_depth + sub_index
```

Once the `new_custody_tree_node` reaches the leaves of the tree, the responder can no longer provide a valid `InteractiveCustodyChallengeResponse`; instead, the responder or the challenger must provide a branch response that provides a branch of the original data tree, at which point the custody leaf equation can be checked and either side of the custody game can "conclusively win".

```python
def process_branch_response(response: BranchResponse,
                            state: State):
    responder = state.validator_registry[response.responder_index]
    challenge_data = responder.interactive_custody_challenge_data
    assert challenge_data.depth == challenge_data.max_depth
    # Verify we're not too late
    assert get_current_epoch(state) < responder.withdrawable_epoch
    # Verify the Merkle branch *of the data tree*
    assert verify_merkle_branch(
        leaf=response.data,
        branch=response.branch,
        depth=challenge_data.max_depth,
        index=challenge_data.offset,
        root=challenge_data.data_root
    )
    # Responder wins
    if hash(challenge_data.responder_subkey + response.data) == challenge_data.current_custody_tree_node:
        penalize_validator(state, challenge_data.challenger_index, response.responder_index)
        responder.interactive_custody_challenge_data = EMPTY_CHALLENGE_DATA
    # Challenger wins
    else:
        penalize_validator(state, response.responder_index, challenge_data.challenger_index)
        state.validator_registry[challenge_data.challenger_index].now_challenging = VALIDATOR_NULL
```

Amend `process_challenge_absences` as follows:

```python
def process_challenge_absences(state: BeaconState) -> None:
    """
    Iterate through the validator registry
    and penalize validators with balance that did not answer challenges.
    """
    for index, validator in enumerate(state.validator_registry):
        if len(validator.open_branch_challenges) > 0 and get_current_epoch(state) > validator.open_branch_challenges[0].inclusion_epoch + CHALLENGE_RESPONSE_DEADLINE:
            penalize_validator(state, index, validator.open_branch_challenges[0].challenger_index)
        if validator.challenge_data.challenger != VALIDATOR_NULL and get_current_epoch(state) > validator.challenge.deadline:
            penalize_validator(state, index, validator.challenge_data.challenger_index)
        if get_current_epoch(state) >= state.validator_registry[validator.now_challenging].withdrawal_epoch:
            penalize_validator(state, index, validator.now_challenging)
            penalize_validator(state, index, validator.challenge_data.challenger_index)
```
