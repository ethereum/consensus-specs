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
        - [Signature domains](#signature-domains)
    - [Data structures](#data-structures)
        - [Custody objects](#custody-objects)
            - [`CustodyChunkChallenge`](#custodychunkchallenge)
            - [`CustodyBitChallenge`](#custodybitchallenge)
            - [`CustodyChunkChallengeRecord`](#custodychunkchallengerecord)
            - [`CustodyBitChallengeRecord`](#custodybitchallengerecord)
            - [`CustodyResponse`](#custodyresponse)
            - [`CustodyKeyReveal`](#custodykeyreveal)
        - [Phase 0 container updates](#phase-0-container-updates)
            - [`Validator`](#validator)
            - [`BeaconState`](#beaconstate)
            - [`BeaconBlockBody`](#beaconblockbody)
    - [Helpers](#helpers)
        - [`get_crosslink_chunk_count`](#get_crosslink_chunk_count)
        - [`get_custody_chunk_bit`](#get_custody_chunk_bit)
        - [`epoch_to_custody_period`](#epoch_to_custody_period)
        - [`verify_custody_key`](#verify_custody_key)
    - [Per-block processing](#per-block-processing)
        - [Operations](#operations)
            - [Custody reveals](#custody-reveals)
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
| `EPOCHS_PER_CUSTODY_PERIOD` | `2**11` (= 2,048) | epochs | ~9 days |
| `CUSTODY_RESPONSE_DEADLINE` | `2**14` (= 16,384) | epochs | ~73 days |

### Max operations per block

| Name | Value |
| - | - |
| `MAX_CUSTODY_KEY_REVEALS` | `2**4` (= 16) |
| `MAX_CUSTODY_CHUNK_CHALLENGES` | `2**2` (= 4) |
| `MAX_CUSTODY_BIT_CHALLENGES` | `2**2` (= 4) |
| `MAX_CUSTODY_RESPONSES` | `2**5` (= 32) |

### Signature domains

| Name | Value |
| - | - |
| `DOMAIN_CUSTODY_KEY_REVEAL` | `6` |
| `DOMAIN_CUSTODY_BIT_CHALLENGE` | `7` |

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

#### `CustodyKeyReveal`

```python
{
    'revealer_index': ValidatorIndex,
    'period': 'uint64',
    'key': BLSSignature,
    'masker_index': ValidatorIndex,
    'mask': Hash,
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
```

#### `BeaconBlockBody`

```python
    'custody_key_reveals': [CustodyKeyReveal],
    'custody_chunk_challenges': [CustodyChunkChallenge],
    'custody_bit_challenges': [CustodyBitChallenge],
    'custody_responses': [CustodyResponse],
```

## Helpers

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

### `verify_custody_key`

```python
def verify_custody_key(state: BeaconState, reveal: CustodyKeyReveal) -> bool:
    # Case 1: non-masked non-punitive non-early reveal
    pubkeys = [state.validator_registry[reveal.revealer_index].pubkey]
    message_hashes = [hash_tree_root(reveal.period)]

    # Case 2: masked punitive early reveal
    # Masking prevents proposer stealing the whistleblower reward
    # Secure under the aggregate extraction infeasibility assumption
    # See pages 11-12 of https://crypto.stanford.edu/~dabo/pubs/papers/aggreg.pdf
    if reveal.mask != ZERO_HASH:
        pubkeys.append(state.validator_registry[reveal.masker_index].pubkey)
        message_hashes.append(reveal.mask)

    return bls_verify_multiple(
        pubkeys=pubkeys,
        message_hashes=message_hashes,
        signature=reveal.key,
        domain=get_domain(
            fork=state.fork,
            epoch=reveal.period * EPOCHS_PER_CUSTODY_PERIOD,
            domain_type=DOMAIN_CUSTODY_KEY_REVEAL,
        ),
    )
```

## Per-block processing

### Operations

Add the following operations to the per-block processing, in order the given below and after all other operations in phase 0.

#### Custody reveals

Verify that `len(block.body.custody_key_reveals) <= MAX_CUSTODY_KEY_REVEALS`.

For each `reveal` in `block.body.custody_key_reveals`, run the following function:

```python
def process_custody_reveal(state: BeaconState,
                           reveal: CustodyKeyReveal) -> None:
    assert verify_custody_key(state, reveal)
    revealer = state.validator_registry[reveal.revealer_index]
    current_custody_period = epoch_to_custody_period(get_current_epoch(state))

    # Case 1: non-masked non-punitive non-early reveal
    if reveal.mask == ZERO_HASH:
        assert reveal.period == epoch_to_custody_period(revealer.activation_epoch) + revealer.custody_reveal_index
        # Revealer is active or exited
        assert is_active_validator(revealer, get_current_epoch(state)) or revealer.exit_epoch > get_current_epoch(state)
        revealer.custody_reveal_index += 1
        revealer.max_reveal_lateness = max(revealer.max_reveal_lateness, current_custody_period - reveal.period)
        proposer_index = get_beacon_proposer_index(state)
        increase_balance(state, proposer_index, base_reward(state, index) // MINOR_REWARD_QUOTIENT)

    # Case 2: masked punitive early reveal
    else:
        assert reveal.period > current_custody_period
        assert revealer.slashed is False
        slash_validator(state, reveal.revealer_index, reveal.masker_index)
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
    attesters = get_attestation_participants(state, attestation.data, attestation.aggregation_bitfield)
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
    state.custody_chunk_challenge_records.append(CustodyChunkChallengeRecord(
        challenge_index=state.custody_challenge_index,
        challenger_index=get_beacon_proposer_index(state),
        responder_index=challenge.responder_index
        deadline=get_current_epoch(state) + CUSTODY_RESPONSE_DEADLINE,
        crosslink_data_root=challenge.attestation.data.crosslink_data_root,
        depth=depth,
        chunk_index=challenge.chunk_index,
    ))
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
    attesters = get_attestation_participants(state, attestation.data, attestation.aggregation_bitfield)
    assert challenge.responder_index in attesters
    # A validator can be the challenger or responder for at most one challenge at a time
    for record in state.custody_bit_challenge_records:
        assert record.challenger_index != challenge.challenger_index
        assert record.responder_index != challenge.responder_index
    # Verify the responder key
    assert verify_custody_key(state, CustodyKeyReveal(
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
    state.custody_bit_challenge_records.append(CustodyBitChallengeRecord(
        challenge_index=state.custody_challenge_index,
        challenger_index=challenge.challenger_index,
        responder_index=challenge.responder_index,
        deadline=get_current_epoch(state) + CUSTODY_RESPONSE_DEADLINE
        crosslink_data_root=challenge.attestation.crosslink_data_root,
        chunk_bits=challenge.chunk_bits,
        responder_key=challenge.responder_key,
    ))
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
    state.custody_chunk_challenge_records.remove(challenge)
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
    state.custody_bit_challenge_records.remove(challenge)
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
            state.custody_chunk_challenge_records.remove(challenge)

    for challenge in state.custody_bit_challenge_records:
        if get_current_epoch(state) > challenge.deadline:
            slash_validator(state, challenge.responder_index, challenge.challenger_index)
            state.custody_bit_challenge_records.remove(challenge)
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
