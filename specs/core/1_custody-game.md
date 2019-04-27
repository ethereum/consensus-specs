# Ethereum 2.0 Phase 1 -- Custody Game

**NOTICE**: This spec is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

- [Ethereum 2.0 Phase 1 -- Custody Game](#ethereum-20-phase-1----custody-game)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Terminology](#terminology)
    - [Constants](#constants)
        - [Misc](#misc)
        - [Time parameters](#time-parameters)
        - [Max operations per block](#max-operations-per-block)
        - [Reward and penalty quotients](#reward-and-penalty-quotients)
        - [Signature domains](#signature-domains)
    - [Data structures](#data-structures)
        - [Custody objects](#custody-objects)
            - [`CustodyChunkChallenge`](#custodychunkchallenge)
            - [`CustodyBitChallenge`](#custodybitchallenge)
            - [`CustodyChunkChallengeRecord`](#custodychunkchallengerecord)
            - [`CustodyBitChallengeRecord`](#custodybitchallengerecord)
            - [`CustodyResponse`](#custodyresponse)
        - [New Beacon operations](#new-beacon-operations)
            - [`RandaoKeyReveal`](#RandaoKeyReveal)
        - [Phase 0 container updates](#phase-0-container-updates)
            - [`Validator`](#validator)
            - [`BeaconState`](#beaconstate)
            - [`BeaconBlockBody`](#beaconblockbody)
    - [Helpers](#helpers)
        - [`typeof`](#typeof)
        - [`empty`](#empty)
        - [`get_crosslink_chunk_count`](#get_crosslink_chunk_count)
        - [`get_custody_chunk_bit`](#get_custody_chunk_bit)
        - [`epoch_to_custody_period`](#epoch_to_custody_period)
        - [`replace_empty_or_append`](#replace_empty_or_append)
        - [`verify_custody_key`](#verify_custody_key)
    - [Per-block processing](#per-block-processing)
        - [Operations](#operations)
            - [Custody key reveals](#custody-key-reveals)
            - [Randao key reveals](#randao-key-reveals)
            - [Chunk challenges](#chunk-challenges)
            - [Bit challenges](#bit-challenges)
            - [Custody responses](#custody-responses)
    - [Per-epoch processing](#per-epoch-processing)

<!-- /TOC -->

## Introduction

This document details the beacon chain additions and changes in Phase 1 of Ethereum 2.0 to support the shard data custody game, building upon the [phase 0](0_beacon-chain.md) specification.

## Terminology

* **Custody game**:
* **Custody period**:
* **Custody chunk**:
* **Custody chunk bit**:
* **Custody chunk challenge**:
* **Custody bit**:
* **Custody bit challenge**:
* **Custody key**:
* **Custody key reveal**:
* **Custody key mask**:
* **Custody response**:
* **Custody response deadline**:

## Constants

### Misc

| Name | Value |
| - | - |
| `BYTES_PER_SHARD_BLOCK` | `2**14` (= 16,384) |
| `BYTES_PER_CUSTODY_CHUNK` | `2**9` (= 512) |
| `MINOR_REWARD_QUOTIENT` | `2**8` (= 256) |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `MAX_CHUNK_CHALLENGE_DELAY` | `2**11` (= 2,048) | epochs | ~9 days |
| `CUSTODY_RESPONSE_DEADLINE` | `2**14` (= 16,384) | epochs | ~73 days |
| `RANDAO_PENALTY_EPOCHS` | `2` | epochs | 12.8 minutes |
| `RANDAO_PENALTY_MAX_FUTURE_EPOCHS` | `2**14` | epochs | ~73 days |
| `EPOCHS_PER_CUSTODY_PERIOD` | `2**11` (= 2,048) | epochs | ~9 days |
| `CUSTODY_PERIOD_TO_RANDAO_PADDING` | `2**11` (= 2,048) | epochs | ~9 days |

### Max operations per block

| Name | Value |
| - | - |
| `MAX_RANDAO_KEY_REVEALS` | `2**4` (= 16) |
| `MAX_CUSTODY_CHUNK_CHALLENGES` | `2**2` (= 4) |
| `MAX_CUSTODY_BIT_CHALLENGES` | `2**2` (= 4) |
| `MAX_CUSTODY_RESPONSES` | `2**5` (= 32) |

### Reward and penalty quotients

| `RANDAO_KEY_REVEAL_SLOT_REWARD_MULTIPLE` | `2` |

### Signature domains

| Name | Value |
| - | - |
| `DOMAIN_CUSTODY_BIT_CHALLENGE` | `6` |

## Data structures

### Custody objects

#### `CustodyChunkChallenge`

```python
{
    'responder_index': ValidatorIndex,
    'attestation': Attestation,
    'chunk_index': 'uint64',
}
```

#### `CustodyBitChallenge`

```python
{
    'responder_index': ValidatorIndex,
    'attestation': Attestation,
    'challenger_index': ValidatorIndex,
    'responder_key': BLSSignature,
    'chunk_bits': Bitfield,
    'signature': BLSSignature,
}
```

#### `CustodyChunkChallengeRecord`

```python
{
    'challenge_index': 'uint64',
    'challenger_index': ValidatorIndex,
    'responder_index': ValidatorIndex,
    'deadline': Epoch,
    'crosslink_data_root': Hash,
    'depth': 'uint64',
    'chunk_index': 'uint64',
}
```

#### `CustodyBitChallengeRecord`

```python
{
    'challenge_index': 'uint64',
    'challenger_index': ValidatorIndex,
    'responder_index': ValidatorIndex,
    'deadline': Epoch,
    'crosslink_data_root': Hash,
    'chunk_bits': Bitfield,
    'responder_key': BLSSignature,
}
```

#### `CustodyResponse`

```python
{
    'challenge_index': 'uint64',
    'chunk_index': 'uint64',
    'chunk': ['byte', BYTES_PER_CUSTODY_CHUNK],
    'branch': [Hash],
}
```

### New Beacon operations

#### `RandaoKeyReveal`

```python
{
    # Index of the validator whos key is being revealed
    'revealed_index': 'uint64',
    # RANDAO epoch of the key that is being revealed
    'epoch': 'uint64',
    # Reveal (masked signature)
    'reveal': 'bytes96',
    # Index of the validator who revealed (whistleblower)
    'masker_index': 'uint64',
    # Mask used to hide the actual reveal signature (prevent reveal from being stolen)
    'mask': 'bytes32',
}
```

### Phase 0 container updates

Add the following fields to the end of the specified container objects. Fields with underlying type `uint64` are initialized to `0` and list fields are initialized to `[]`.

#### `Validator`

```python
    'custody_reveal_index': 'uint64',
    'max_reveal_lateness': 'uint64',
```

#### `BeaconState`

```python
    'custody_chunk_challenge_records': [CustodyChunkChallengeRecord],
    'custody_bit_challenge_records': [CustodyBitChallengeRecord],
    'custody_challenge_index': 'uint64',

    # Future RANDAO reveals already exposed; contains the indices of the exposed validator
    # at RANDAO reveal period % RANDAO_PENALTY_MAX_FUTURE_EPOCHS
    'exposed_randao_reveals': [['uint64'], RANDAO_PENALTY_MAX_FUTURE_EPOCHS],
```

#### `BeaconBlockBody`

```python
    'custody_chunk_challenges': [CustodyChunkChallenge],
    'custody_bit_challenges': [CustodyBitChallenge],
    'custody_responses': [CustodyResponse],
    'randao_key_reveals': [RandaoKeyReveal],
```

## Helpers

### `typeof`

The `typeof` function accepts and SSZ object as a single input and returns the corresponding SSZ type.

### `empty`

The `empty` function accepts and SSZ type as input and returns an object of that type with all fields initialized to default values.

### `get_crosslink_chunk_count`

```python
def get_custody_chunk_count(attestation: Attestation) -> int:
    crosslink_start_epoch = attestation.data.latest_crosslink.epoch
    crosslink_end_epoch = slot_to_epoch(attestation.data.slot)
    crosslink_crosslink_length = min(MAX_CROSSLINK_EPOCHS, end_epoch - start_epoch)
    chunks_per_epoch = 2 * BYTES_PER_SHARD_BLOCK * SLOTS_PER_EPOCH // BYTES_PER_CUSTODY_CHUNK
    return crosslink_crosslink_length * chunks_per_epoch
```

### `get_custody_chunk_bit`

```python
def get_custody_chunk_bit(key: BLSSignature, chunk: bytes) -> bool:
    # TODO: Replace with something MPC-friendly, e.g. the Legendre symbol
    return get_bitfield_bit(hash(challenge.responder_key + chunk), 0)
```

### `epoch_to_custody_period`

```python
def epoch_to_custody_period(epoch: Epoch) -> int:
    return epoch // EPOCHS_PER_CUSTODY_PERIOD
```

### `get_randao_epoch_for_custody_period`

```python
def get_randao_epoch_for_custody_period(period: int) -> Epoch:
    return period * EPOCHS_PER_CUSTODY_PERIOD + CUSTODY_PERIOD_TO_RANDAO_PADDING
### `replace_empty_or_append`

```python
def replace_empty_or_append(list: List[Any], new_element: Any) -> int:
    for i in range(len(list)):
        if list[i] == empty(typeof(new_element)):
            list[i] = new_element
            return i
    list.append(new_element)
    return len(list) - 1
```

### `verify_custody_key`

```python
def verify_custody_key(state: BeaconState, reveal: RandaoKeyReveal) -> bool:
    epoch_to_sign = get_randao_epoch_for_custody_period(reveal.period)
    pubkeys = [state.validator_registry[reveal.revealer_index].pubkey]
    message_hashes = [hash_tree_root(epoch_to_sign)]

    return bls_verify_multiple(
        pubkeys=pubkeys,
        message_hashes=message_hashes,
        signature=reveal.key,
        domain=get_domain(
            fork=state.fork,
            epoch=epoch_to_sign * EPOCHS_PER_CUSTODY_PERIOD,
            domain_type=DOMAIN_RANDAO,
        ),
    )
```

## Per-block processing

### Operations

Add the following operations to the per-block processing, in order the given below and after all other operations in phase 0.

#### Custody reveals

Replace process_custody_reveal from phase 0 with this function:

```python
def process_custody_reveal(state: BeaconState,
                           reveal: RandaoKeyReveal) -> None:
    assert verify_custody_key(state, reveal)
    revealer = state.validator_registry[reveal.revealer_index]
    current_custody_period = epoch_to_custody_period(get_current_epoch(state))

    assert reveal.period == epoch_to_custody_period(revealer.activation_epoch) + revealer.custody_reveal_index
    # Revealer is active or exited
    assert is_active_validator(revealer, get_current_epoch(state)) or revealer.exit_epoch > get_current_epoch(state)
    revealer.custody_reveal_index += 1
    revealer.max_reveal_lateness = max(revealer.max_reveal_lateness, current_custody_period - reveal.period)
    proposer_index = get_beacon_proposer_index(state)
    increase_balance(state, proposer_index, base_reward(state, index) // MINOR_REWARD_QUOTIENT)
```

##### Randao key reveals

Verify that `len(block.body.randao_key_reveals) <= MAX_RANDAO_KEY_REVEALS`.

For each `randao_key_reveal` in `block.body.randao_key_reveal`, run the following function:

```python
def process_randao_key_reveal(state: BeaconState,
                              randao_key_reveal: RandaoKeyReveal) -> None:
    """
    Process ``RandaoKeyReveal`` operation.
    Note that this function mutates ``state``.
    """
    if randao_key_reveal.mask == ZERO_HASH:
        process_custody_reveal(state, randao_key_reveal)

    revealer = state.validator_registry[randao_key_reveal.revealed_index]
    masker = state.validator_registry[randao_key_reveal.masker_index]
    pubkeys = [revealer.pubkey, masker.pubkey]
    message_hashes = [
        hash_tree_root(randao_key_reveal.epoch),
        randao_key_reveal.mask,
    ]

    assert randao_key_reveal.epoch >= get_current_epoch(state) + RANDAO_PENALTY_EPOCHS
    assert randao_key_reveal.epoch < get_current_epoch(state) + RANDAO_PENALTY_MAX_FUTURE_EPOCHS
    assert revealer.slashed is False
    assert randao_key_reveal.revealed_index not in state.exposed_randao_reveals[randao_key_reveal.epoch % RANDAO_PENALTY_MAX_FUTURE_EPOCHS]

    assert bls_verify_multiple(
        pubkeys=pubkeys,
        message_hashes=message_hashes,
        signature=randao_key_reveal.reveal,
        domain=get_domain(
            state=state,
            domain_type=DOMAIN_RANDAO,
            message_epoch=randao_key_reveal.epoch,
        ),
    )

    if randao_key_reveal.epoch >= get_current_epoch(state) + CUSTODY_PERIOD_TO_RANDAO_PADDING:
        # Full slashing when the RANDAO was revealed so early it may be a valid custody
        # round key
        slash_validator(state, randao_key_reveal.revealed_index, randao_key_reveal.masker_index)
    else:
        # Only a small penalty proportional to proposer slot reward for RANDAO reveal 
        # that does not interfere with the custody period
        # The penalty is proportional to the max proposer reward 
        
        # Calculate penalty
        max_proposer_slot_reward = (
            get_base_reward(state, randao_key_reveal.revealed_index) *
            SLOTS_PER_EPOCH //
            len(get_active_validator_indices(state, get_current_epoch(state))) //
            PROPOSER_REWARD_QUOTIENT
        )
        penalty = max_proposer_slot_reward * RANDAO_KEY_REVEAL_SLOT_REWARD_MULTIPLE

        # Apply penalty
        proposer_index = get_beacon_proposer_index(state)
        whistleblower_index = randao_key_reveal.masker_index
        whistleblowing_reward = penalty // WHISTLEBLOWING_REWARD_QUOTIENT
        proposer_reward = whistleblowing_reward // PROPOSER_REWARD_QUOTIENT
        increase_balance(state, proposer_index, proposer_reward)
        increase_balance(state, whistleblower_index, whistleblowing_reward - proposer_reward)
        decrease_balance(state, randao_key_reveal.revealed_index, penalty)

        # Mark this RANDAO reveal as exposed so validator cannot be punished repeatedly 
        state.exposed_randao_reveals[randao_key_reveal.epoch % RANDAO_PENALTY_MAX_FUTURE_EPOCHS].append(randao_key_reveal.revealed_index)

```

#### Chunk challenges

Verify that `len(block.body.custody_chunk_challenges) <= MAX_CUSTODY_CHUNK_CHALLENGES`.

For each `challenge` in `block.body.custody_chunk_challenges`, run the following function:

```python
def process_chunk_challenge(state: BeaconState,
                            challenge: CustodyChunkChallenge) -> None:
    # Verify the attestation
    assert verify_standalone_attestation(state, convert_to_standalone(state, challenge.attestation))
    # Verify it is not too late to challenge
    assert slot_to_epoch(challenge.attestation.data.slot) >= get_current_epoch(state) - MAX_CHUNK_CHALLENGE_DELAY
    responder = state.validator_registry[challenge.responder_index]
    assert responder.exit_epoch >= get_current_epoch(state) - MAX_CHUNK_CHALLENGE_DELAY
    # Verify the responder participated in the attestation
    attesters = get_attesting_indices(state, attestation.data, attestation.aggregation_bitfield)
    assert challenge.responder_index in attesters
    # Verify the challenge is not a duplicate
    for record in state.custody_chunk_challenge_records:
        assert (
            record.crosslink_data_root != challenge.attestation.data.crosslink_data_root or
            record.chunk_index != challenge.chunk_index
        )
    # Verify depth
    depth = math.log2(next_power_of_two(get_custody_chunk_count(challenge.attestation)))
    assert challenge.chunk_index < 2**depth
    # Add new chunk challenge record
    new_record = CustodyChunkChallengeRecord(
        challenge_index=state.custody_challenge_index,
        challenger_index=get_beacon_proposer_index(state),
        responder_index=challenge.responder_index
        deadline=get_current_epoch(state) + CUSTODY_RESPONSE_DEADLINE,
        crosslink_data_root=challenge.attestation.data.crosslink_data_root,
        depth=depth,
        chunk_index=challenge.chunk_index,
    )
    replace_empty_or_append(state.custody_chunk_challenge_records, new_record)

    state.custody_challenge_index += 1
    # Postpone responder withdrawability
    responder.withdrawable_epoch = FAR_FUTURE_EPOCH
```

#### Bit challenges

Verify that `len(block.body.custody_bit_challenges) <= MAX_CUSTODY_BIT_CHALLENGES`.

For each `challenge` in `block.body.custody_bit_challenges`, run the following function:

```python
def process_bit_challenge(state: BeaconState,
                          challenge: CustodyBitChallenge) -> None:
    # Verify challenge signature
    challenger = state.validator_registry[challenge.challenger_index]
    assert bls_verify(
        pubkey=challenger.pubkey,
        message_hash=signing_root(challenge),
        signature=challenge.signature,
        domain=get_domain(state, get_current_epoch(state), DOMAIN_CUSTODY_BIT_CHALLENGE),
    )
    # Verify the challenger is not slashed
    assert challenger.slashed is False
    # Verify the attestation
    assert verify_standalone_attestation(state, convert_to_standalone(state, challenge.attestation))
    # Verify the attestation is eligible for challenging
    responder = state.validator_registry[challenge.responder_index]
    min_challengeable_epoch = responder.exit_epoch - EPOCHS_PER_CUSTODY_PERIOD * (1 + responder.max_reveal_lateness)
    assert min_challengeable_epoch <= slot_to_epoch(challenge.attestation.data.slot)
    # Verify the responder participated in the attestation
    attesters = get_attesting_indices(state, attestation.data, attestation.aggregation_bitfield)
    assert challenge.responder_index in attesters
    # A validator can be the challenger or responder for at most one challenge at a time
    for record in state.custody_bit_challenge_records:
        assert record.challenger_index != challenge.challenger_index
        assert record.responder_index != challenge.responder_index
    # Verify the responder key
    assert verify_custody_key(state, RandaoKeyReveal(
        revealer_index=challenge.responder_index,
        period=epoch_to_custody_period(slot_to_epoch(attestation.data.slot)),
        key=challenge.responder_key,
        masker_index=0,
        mask=ZERO_HASH,
    ))
    # Verify the chunk count
    chunk_count = get_custody_chunk_count(challenge.attestation)
    assert verify_bitfield(challenge.chunk_bits, chunk_count)
    # Verify the xor of the chunk bits does not equal the custody bit
    chunk_bits_xor = 0b0
    for i in range(chunk_count):
        chunk_bits_xor ^ get_bitfield_bit(challenge.chunk_bits, i)
    custody_bit = get_bitfield_bit(attestation.custody_bitfield, attesters.index(responder_index))
    assert custody_bit != chunk_bits_xor
    # Add new bit challenge record
    new_record = CustodyBitChallengeRecord(
        challenge_index=state.custody_challenge_index,
        challenger_index=challenge.challenger_index,
        responder_index=challenge.responder_index,
        deadline=get_current_epoch(state) + CUSTODY_RESPONSE_DEADLINE
        crosslink_data_root=challenge.attestation.crosslink_data_root,
        chunk_bits=challenge.chunk_bits,
        responder_key=challenge.responder_key,
    )
    replace_empty_or_append(state.custody_bit_challenge_records, new_record)
    state.custody_challenge_index += 1
    # Postpone responder withdrawability
    responder.withdrawable_epoch = FAR_FUTURE_EPOCH
```

#### Custody responses

Verify that `len(block.body.custody_responses) <= MAX_CUSTODY_RESPONSES`.

For each `response` in `block.body.custody_responses`, run the following function:

```python
def process_custody_response(state: BeaconState,
                             response: CustodyResponse) -> None:
    chunk_challenge = next(record for record in state.custody_chunk_challenge_records if record.challenge_index == response.challenge_index, None)
    if chunk_challenge is not None:
        return process_chunk_challenge_response(state, response, chunk_challenge)

    bit_challenge = next(record for record in state.custody_bit_challenge_records if record.challenge_index == response.challenge_index, None)
    if bit_challenge is not None:
        return process_bit_challenge_response(state, response, bit_challenge)

    assert False
```

```python
def process_chunk_challenge_response(state: BeaconState,
                                     response: CustodyResponse,
                                     challenge: CustodyChunkChallengeRecord) -> None:
    # Verify chunk index
    assert response.chunk_index == challenge.chunk_index
    # Verify the chunk matches the crosslink data root
    assert verify_merkle_branch(
        leaf=hash_tree_root(response.chunk),
        branch=response.branch,
        depth=challenge.depth,
        index=response.chunk_index,
        root=challenge.crosslink_data_root,
    )
    # Clear the challenge
    records = state.custody_chunk_challenge_records
    records[records.index(challenge)] = CustodyChunkChallengeRecord()
    # Reward the proposer
    proposer_index = get_beacon_proposer_index(state)
    increase_balance(state, proposer_index, base_reward(state, index) // MINOR_REWARD_QUOTIENT)
```

```python
def process_bit_challenge_response(state: BeaconState,
                                   response: CustodyResponse,
                                   challenge: CustodyBitChallengeRecord) -> None:
    # Verify chunk index
    assert response.chunk_index < len(challenge.chunk_bits)
    # Verify the chunk matches the crosslink data root
    assert verify_merkle_branch(
        leaf=hash_tree_root(response.chunk),
        branch=response.branch,
        depth=math.log2(next_power_of_two(len(challenge.chunk_bits))),
        index=response.chunk_index,
        root=challenge.crosslink_data_root,
    )
    # Verify the chunk bit does not match the challenge chunk bit
    assert get_custody_chunk_bit(challenge.responder_key, response.chunk) != get_bitfield_bit(challenge.chunk_bits, response.chunk_index)
    # Clear the challenge
    records = state.custody_bit_challenge_records
    records[records.index(challenge)] = CustodyBitChallengeRecord()
    # Slash challenger
    slash_validator(state, challenge.challenger_index, challenge.responder_index)
```

## Per-epoch processing

Run `process_challenge_deadlines(state)` immediately after `process_ejections(state)`:

```python
def process_challenge_deadlines(state: BeaconState) -> None:
    for challenge in state.custody_chunk_challenge_records:
        if get_current_epoch(state) > challenge.deadline:
            slash_validator(state, challenge.responder_index, challenge.challenger_index)
            records = state.custody_chunk_challenge_records
            records[records.index(challenge)] = CustodyChunkChallengeRecord()

    for challenge in state.custody_bit_challenge_records:
        if get_current_epoch(state) > challenge.deadline:
            slash_validator(state, challenge.responder_index, challenge.challenger_index)
            records = state.custody_bit_challenge_records
            records[records.index(challenge)] = CustodyBitChallengeRecord()
```

Run `clean_up_exposed_randao_key_reveals(state)` after `process_final_updates(state)`:

```python
def clean_up_exposed_randao_key_reveals(state: BeaconState) -> None:

    # Clean up exposed RANDAO key reveals
    state.exposed_randao_reveals[current_epoch % RANDAO_PENALTY_MAX_FUTURE_EPOCHS] = []
```

In `process_penalties_and_exits`, change the definition of `eligible` to the following (note that it is not a pure function because `state` is declared in the surrounding scope):

```python
def eligible(index):
    validator = state.validator_registry[index]
    # Cannot exit if there are still open chunk challenges
    if len([record for record in state.custody_chunk_challenge_records if record.responder_index == index]) > 0:
        return False
    # Cannot exit if you have not revealed all of your custody keys
    elif epoch_to_custody_period(revealer.activation_epoch) + validator.custody_reveal_index <= epoch_to_custody_period(validator.exit_epoch):
        return False
    # Cannot exit if you already have
    elif validator.withdrawable_epoch < FAR_FUTURE_EPOCH:
        return False
    # Return minimum time
    else:
        return current_epoch >= validator.exit_epoch + MIN_VALIDATOR_WITHDRAWAL_EPOCHS
```
