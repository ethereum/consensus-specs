# Ethereum 2.0 Phase 1 -- Shard Data Chains

###### tags: `spec`, `eth2.0`, `casper`, `sharding`

**NOTICE**: This document is a work-in-progress for researchers and implementers. It reflects recent spec changes and takes precedence over the [Python proof-of-concept implementation](https://github.com/ethereum/beacon_chain).

### Introduction

This document represents the specification for Phase 1 of Ethereum 2.0 -- Shard Data Chains. Phase 1 depends on the implementation of [Phase 0 -- The Beacon Chain](0_beacon-chain.md).

Ethereum 2.0 consists of a central beacon chain along with `SHARD_COUNT` shard chains. Phase 1 is primarily concerned with the construction, validity, and consensus on the _data_ of these shard chains. Phase 1 does not specify shard chain state execution or account balances. This is left for future phases.

### Terminology

### Constants

Phase 1 depends upon all of the constants defined in [Phase 0](0_beacon-chain.md#constants) in addition to the following:

| Constant                     | Value           | Unit   | Approximation |
|------------------------------|-----------------|--------|---------------|
| `SHARD_CHUNK_SIZE`           | 2**5 (= 32)     | bytes  |               |
| `SHARD_BLOCK_SIZE`           | 2**14 (= 16384) | bytes  |               |
| `CROSSLINK_LOOKBACK`         | 2**5 (= 32)     | slots  |               |
| `MAX_BRANCH_CHALLENGE_DELAY` | 2**11 (= 2048)  | epochs | 9 days        |
| `CHALLENGE_RESPONSE_DEADLINE`| 2**14 (= 16384) | epochs | 73 days       |
| `MAX_BRANCH_CHALLENGES`      | 2**2 (= 4)      |        |               |
| `MAX_BRANCH_RESPONSES`       | 2**4 (= 16)     |        |               |
| `MAX_EARLY_SUBKEY_REVEALS`   | 2**4 (= 16)     |        |               |
| `CUSTODY_PERIOD_LENGTH`      | 2**11 (= 2048)  | epochs | 9 days        |
| `MINOR_REWARD_QUOTIENT`      | 2**8 (= 256)    |        |               |

### Flags, domains, etc.

| Constant               | Value           |
|------------------------|-----------------|
| `SHARD_PROPOSER_DOMAIN`| 129             |
| `SHARD_ATTESTER_DOMAIN`| 130             |
| `DOMAIN_CUSTODY_SUBKEY`| 131             |

## Data Structures

### Shard chain blocks

A `ShardBlock` object has the following fields:

```python
{
    # Slot number
    'slot': 'uint64',
    # What shard is it on
    'shard_id': 'uint64',
    # Parent block's hash of root
    'parent_root': 'hash32',
    # Beacon chain block
    'beacon_chain_ref': 'hash32',
    # Depth of the Merkle tree
    'data_tree_depth': 'uint8',
    # Merkle root of data
    'data_root': 'hash32'
    # State root (placeholder for now)
    'state_root': 'hash32',
    # Block signature
    'signature': ['uint384'],
    # Attestation
    'participation_bitfield': 'bytes',
    'aggregate_signature': ['uint384'],
}
```

## Shard block processing

For a block on a shard to be processed by a node, the following conditions must be met:

* The `ShardBlock` pointed to by `parent_root` has already been processed and accepted
* The signature for the block from the _proposer_ (see below for definition) of that block is included along with the block in the network message object

To validate a block header on shard `shard_id`, compute as follows:

* Verify that `beacon_chain_ref` is the hash of a block in the beacon chain with slot less than or equal to `slot`. Verify that `beacon_chain_ref` is equal to or a descendant of the `beacon_chain_ref` specified in the `ShardBlock` pointed to by `parent_root`.
* Let `state` be the state of the beacon chain block referred to by `beacon_chain_ref`. Let `validators` be `[validators[i] for i in state.current_persistent_committees[shard_id]]`.
* Assert `len(participation_bitfield) == ceil_div8(len(validators))`
* Let `proposer_index = hash(state.randao_mix + int_to_bytes8(shard_id) + int_to_bytes8(slot)) % len(validators)`. Let `msg` be the block but with the `block.signature` set to `[0, 0]`. Verify that `BLSVerify(pub=validators[proposer_index].pubkey, msg=hash(msg), sig=block.signature, domain=get_domain(state, slot, SHARD_PROPOSER_DOMAIN))` passes.
* Generate the `group_public_key` by adding the public keys of all the validators for whom the corresponding position in the bitfield is set to 1. Verify that `BLSVerify(pub=group_public_key, msg=parent_root, sig=block.aggregate_signature, domain=get_domain(state, slot, SHARD_ATTESTER_DOMAIN))` passes.

### Block Merklization helper

```python
def merkle_root(block_body):
    assert len(block_body) == SHARD_BLOCK_SIZE
    chunks = SHARD_BLOCK_SIZE // SHARD_CHUNK_SIZE
    o = [0] * chunks + [block_body[i * SHARD_CHUNK_SIZE: (i+1) * SHARD_CHUNK_SIZE] for i in range(chunks)]
    for i in range(chunks-1, 0, -1):
        o[i] = hash(o[i*2] + o[i*2+1])
    return o[1]
```

### Verifying shard block data

At network layer, we expect a shard block header to be broadcast along with its `block_body`.

* Verify that `len(block_body) == SHARD_BLOCK_SIZE`
* Verify that `merkle_root(block_body)` equals the `data_root` in the header.

### Verifying a crosslink

A node should sign a crosslink only if the following conditions hold. **If a node has the capability to perform the required level of verification, it should NOT follow chains on which a crosslink for which these conditions do NOT hold has been included, or a sufficient number of signatures have been included that during the next state recalculation, a crosslink will be registered.**

First, the conditions must recursively apply to the crosslink referenced in `last_crosslink_root` for the same shard (unless `last_crosslink_root` equals zero, in which case we are at the genesis).

Second, we verify the `shard_chain_commitment`.
* Let `start_slot = state.latest_crosslinks[shard].epoch * EPOCH_LENGTH + EPOCH_LENGTH - CROSSLINK_LOOKBACK`.
* Let `end_slot = attestation.data.slot - attestation.data.slot % EPOCH_LENGTH - CROSSLINK_LOOKBACK`.
* Let `length = end_slot - start_slot`, `headers[0] .... headers[length-1]` be the serialized block headers in the canonical shard chain from the verifer's point of view (note that this implies that `headers` and `bodies` have been checked for validity).
* Let `bodies[0] ... bodies[length-1]` be the bodies of the blocks.
* Note: If there is a missing slot, then the header and body are the same as that of the block at the most recent slot that has a block.

We define two helpers:

```python
def pad_to_power_of_2(values: List[bytes]) -> List[bytes]:
    while not is_power_of_two(len(values)):
        values = values + [SHARD_BLOCK_SIZE]
    return values
```

```python
def merkle_root_of_bytes(data: bytes) -> bytes:
    return merkle_root([data[i:i+32] for i in range(0, len(data), 32)])
```

We define the function for computing the commitment as follows:

```python
def compute_commitment(headers: List[ShardBlock], bodies: List[bytes]) -> Bytes32:
    return hash(
        merkle_root(pad_to_power_of_2([merkle_root_of_bytes(zpad(serialize(h), SHARD_BLOCK_SIZE)) for h in headers])),
        merkle_root(pad_to_power_of_2([merkle_root_of_bytes(h) for h in bodies]))
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
    'open_branch_challenges': [BranchChallengeRecord],
    'next_subkey_to_reveal': 'uint64',
    'reveal_max_periods_late': 'uint64'
```

And the initializers:

```python
    'open_branch_challenges': [],
    'next_subkey_to_reveal': 0,
    'reveal_max_periods_late': 0,
```

Rename `withdrawal_epoch` to `withdrawable_epoch`.

### `BranchChallengeRecord`

Define a `BranchChallengeRecord` as follows:

```python
{
    'challenger_index': 'uint64',
    'root': 'bytes32',
    'depth': 'uint64',
    'inclusion_epoch': 'uint64',
    'data_index': 'uint64'
}
```

### `BeaconBlockBody`

Add two member values to the `BeaconBlockBody` structure:

```python
    'branch_challenges': [BranchChallenge],
    'branch_responses': [BranchResponse],
    'subkey_reveals': [SubkeyReveal],
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
    'responder_index': 'uint64',
    'data': 'bytes32',
    'branch': ['bytes32'],
    'data_index': 'uint64',
    'root': 'bytes32'
}
```

### `SubkeyReveal`

Define a `SubkeyReveal` as follows:

```python
{
    'validator_index': 'uint64',
    'period': 'uint64',
    'subkey': 'bytes96'
}
```

## Helpers

### `get_current_custody_period`

```python
def get_current_custody_period(state: BeaconState) -> int:
    return get_current_epoch(state) // CUSTODY_PERIOD_LENGTH
```

### `verify_custody_subkey`

```python
def verify_custody_subkey(pubkey: bytes48, subkey: bytes96, period: int) -> bool:
    return bls_verify(
        pubkey=pubkey,
        message_hash=hash(int_to_bytes8(period)),
        signature=subkey,
        domain=get_domain(
            state.fork,
            period * CUSTODY_PERIOD_LENGTH,
            DOMAIN_CUSTODY_SUBKEY
        )
    )
```

### `prepare_validator_for_withdrawal`

Change the definition of `prepare_validator_for_withdrawal` as follows:

```python
def prepare_validator_for_withdrawal(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Set the validator with the given ``index`` with ``WITHDRAWABLE`` flag.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[index]
    validator.withdrawable_epoch = get_current_epoch(state) + MIN_VALIDATOR_WITHDRAWAL_EPOCHS
```

### `penalize_validator`

Change the definition of `penalize_validator` as follows:

```python
def penalize_validator(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Penalize the validator of the given ``index``.
    Note that this function mutates ``state``.
    """
    exit_validator(state, index)
    validator = state.validator_registry[index]
    state.latest_penalized_balances[get_current_epoch(state) % LATEST_PENALIZED_EXIT_LENGTH] += get_effective_balance(state, index)

    whistleblower_index = get_beacon_proposer_index(state, state.slot)
    whistleblower_reward = get_effective_balance(state, index) // WHISTLEBLOWER_REWARD_QUOTIENT
    state.validator_balances[whistleblower_index] += whistleblower_reward
    state.validator_balances[index] -= whistleblower_reward
    validator.penalized_epoch = get_current_epoch(state)
    validator.withdrawable_epoch = get_current_epoch(state) + LATEST_PENALIZED_EXIT_LENGTH
```

## Per-slot processing

### Operations

Add the following operations to the per-slot processing, in order given below and _following_ all other operations (specifically, right after exits) as follows.

#### Branch challenges

Verify that `len(block.body.branch_challenges) <= MAX_BRANCH_CHALLENGES`.

For each `challenge` in `block.body.branch_challenges`:

* Verify that `slot_to_epoch(challenge.attestation.data.slot) >= get_current_epoch(state) - MAX_BRANCH_CHALLENGE_DELAY`.
* Verify that `state.validator_registry[responder_index].exit_epoch >= get_current_epoch(state) - MAX_BRANCH_CHALLENGE_DELAY`.
* Verify that `verify_slashable_attestation(state, challenge.attestation)` returns `True`.
* Verify that `challenge.responder_index` is in `challenge.attestation.validator_indices`.
* Let `depth = log2(next_power_of_two(SHARD_BLOCK_SIZE // 32 * EPOCH_LENGTH * (slot_to_epoch(challenge.attestation.data.slot) - challenge.attestation.latest_crosslink.epoch)`. Verify that `challenge.data_index < 2**depth`.
* Verify that there does not exist a `BranchChallengeRecord` in `state.validator_registry[challenge.responder_index].open_branch_challenges` with `root == challenge.attestation.data.shard_chain_commitment` and `data_index == data_index`.
* Append to `state.validator_registry[challenge.responder_index].open_branch_challenges` the object `BranchChallengeRecord(challenger_index=get_beacon_proposer_index(state, state.slot), root=challenge.attestation.data.shard_chain_commitment, depth=depth, inclusion_epoch=get_current_epoch(state), data_index=data_index)`.

**Invariant**: the `open_branch_challenges` array will always stay sorted in order of `inclusion_epoch`.

#### Branch responses

Verify that `len(block.body.branch_responses) <= MAX_BRANCH_RESPONSES`.

For each `response` in `block.body.branch_responses`:

* Find the `BranchChallengeRecord` in `state.validator_registry[response.responder_index].open_branch_challenges` whose (`root`, `data_index`) match the (`root`, `data_index`) of the `response`. Verify that one such record exists (it is not possible for there to be more than one), call it `record`.
* Verify that `verify_merkle_branch(leaf=response.data, branch=response.branch, depth=record.depth, index=record.data_index, root=record.root)` is True.
* Verify that `get_current_epoch(state) >= record.inclusion_epoch + ENTRY_EXIT_DELAY`.
* Remove the `record` from `state.validator_registry[response.responder_index].open_branch_challenges`
* Determine the proposer `proposer_index = get_beacon_proposer_index(state, state.slot)` and set `state.validator_balances[proposer_index] += base_reward(state, index) // MINOR_REWARD_QUOTIENT`.

#### Subkey reveals

Verify that `len(block.body.early_subkey_reveals) <= MAX_EARLY_SUBKEY_REVEALS`.

For each `reveal` in `block.body.early_subkey_reveals`:

* Verify that `verify_custody_subkey(state.validator_registry[reveal.validator_index].pubkey, reveal.subkey, reveal.period)` returns `True`.
* Let `is_early_reveal = reveal.period > get_current_custody_period(state) or (reveal.period == get_current_custody_period(state) and state.validator_registry[reveal.validator_index].exit_epoch > get_current_epoch(state))` (ie. either the reveal is of a future period, or it's of the current period and the validator is still active)
* Verify that one of the following is true:
    * (i) `is_early_reveal` is `True`
    * (ii) `is_early_reveal` is `False` and `reveal.period == state.validator_registry[reveal.validator_index].next_subkey_to_reveal` (revealing a past subkey, or a current subkey for a validator that has exited)

In case (i):

* Verify that `state.validator_registry[reveal.validator_index].penalized_epoch > get_current_epoch(state) + ENTRY_EXIT_DELAY`.
* Run `penalize_validator(state, reveal.validator_index)`.

In case (ii):

* Determine the proposer `proposer_index = get_beacon_proposer_index(state, state.slot)` and set `state.validator_balances[proposer_index] += base_reward(state, index) // MINOR_REWARD_QUOTIENT`.
* Set `state.validator_registry[reveal.validator_index].next_subkey_to_reveal += 1`
* Set `state.validator_registry[reveal.validator_index].reveal_max_periods_late = max(state.validator_registry[reveal.validator_index].reveal_max_periods_late, get_current_period(state) - reveal.period)`.

## Per-epoch processing

Add the following loop immediately below the `process_ejections` loop:

```python
def process_challenge_absences(state: BeaconState) -> None:
    """
    Iterate through the validator registry
    and penalize validators with balance that did not answer challenges.
    """
    for index, validator in enumerate(state.validator_registry):
        if len(validator.open_branch_challenges) > 0 and get_current_epoch(state) > validator.open_branch_challenges[0].inclusion_epoch + CHALLENGE_RESPONSE_DEADLINE:
            penalize_validator(state, index)
```

In `process_penalties_and_exits`, change the definition of `eligible` to the following (note that it is not a pure function because `state` is declared in the surrounding scope):

```python
def eligible(index):
    validator = state.validator_registry[index]
    # Cannot exit if there are still open branch challenges
    if len(validator.open_branch_challenges) > 0:
        return False
    # Cannot exit if you have not revealed all of your subkeys
    elif validator.next_subkey_to_reveal <= validator.exit_epoch // CUSTODY_PERIOD_LENGTH:
        return False
    # Cannot exit if you already have
    elif validator.withdrawable_epoch < FAR_FUTURE_EPOCH:
        return False
    # Return minimum time
    else:
        return current_epoch >= validator.exit_epoch + MIN_VALIDATOR_WITHDRAWAL_EPOCHS
```
