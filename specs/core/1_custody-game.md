# Ethereum 2.0 Phase 1 -- Custody Game

**Notice**: This document is a work-in-progress for researchers and implementers.

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
        - [New beacon operations](#new-beacon-operations)
            - [`CustodyKeyReveal`](#custodykeyreveal)
            - [`EarlyDerivedSecretReveal`](#earlyderivedsecretreveal)
        - [Phase 0 container updates](#phase-0-container-updates)
            - [`Validator`](#validator)
            - [`BeaconState`](#beaconstate)
            - [`BeaconBlockBody`](#beaconblockbody)
    - [Helpers](#helpers)
        - [`typeof`](#typeof)
        - [`empty`](#empty)
        - [`get_crosslink_chunk_count`](#get_crosslink_chunk_count)
        - [`get_custody_chunk_bit`](#get_custody_chunk_bit)
        - [`get_chunk_bits_root`](#get_chunk_bits_root)
        - [`get_randao_epoch_for_custody_period`](#get_randao_epoch_for_custody_period)
        - [`get_validators_custody_reveal_period`](#get_validators_custody_reveal_period)

<!-- /TOC -->

## Introduction

This document details the beacon chain additions and changes in Phase 1 of Ethereum 2.0 to support the shard data custody game, building upon the [Phase 0](0_beacon-chain.md) specification.

## Terminology

* **Custody game**—
* **Custody period**—
* **Custody chunk**—
* **Custody chunk bit**—
* **Custody chunk challenge**—
* **Custody bit**—
* **Custody bit challenge**—
* **Custody key**—
* **Custody key reveal**—
* **Custody key mask**—
* **Custody response**—
* **Custody response deadline**—

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
| `RANDAO_PENALTY_EPOCHS` | `2**1` (= 2) | epochs | 12.8 minutes |
| `EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS` | `2**14` | epochs | ~73 days |
| `EPOCHS_PER_CUSTODY_PERIOD` | `2**11` (= 2,048) | epochs | ~9 days |
| `CUSTODY_PERIOD_TO_RANDAO_PADDING` | `2**11` (= 2,048) | epochs | ~9 days |
| `MAX_REVEAL_LATENESS_DECREMENT` | `2**7` (= 128) | epochs | ~14 hours |

### Max operations per block

| Name | Value |
| - | - |
| `MAX_CUSTODY_KEY_REVEALS` | `2**4` (= 16) |
| `MAX_EARLY_DERIVED_SECRET_REVEALS` | `1` |
| `MAX_CUSTODY_CHUNK_CHALLENGES` | `2**2` (= 4) |
| `MAX_CUSTODY_BIT_CHALLENGES` | `2**2` (= 4) |
| `MAX_CUSTODY_RESPONSES` | `2**5` (= 32) |

### Reward and penalty quotients

| `EARLY_DERIVED_SECRET_REVEAL_SLOT_REWARD_MULTIPLE` | `2**1` (= 2) |

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
    'inclusion_epoch': Epoch,
    'data_root': Hash,
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
    'inclusion_epoch': Epoch,
    'data_root': Hash,
    'chunk_count': 'uint64',
    'chunk_bits_merkle_root': Hash,
    'responder_key': BLSSignature,
}
```

#### `CustodyResponse`

```python
{
    'challenge_index': 'uint64',
    'chunk_index': 'uint64',
    'chunk': ['byte', BYTES_PER_CUSTODY_CHUNK],
    'data_branch': [Hash],
    'chunk_bits_branch': [Hash],
    'chunk_bits_leaf': Hash,
}
```

### New beacon operations

#### `CustodyKeyReveal`

```python
{
    # Index of the validator whose key is being revealed
    'revealer_index': 'uint64',
    # Reveal (masked signature)
    'reveal': 'bytes96',
}
```

#### `EarlyDerivedSecretReveal`

Represents an early (punishable) reveal of one of the derived secrets, where derived secrets are RANDAO reveals and custody reveals (both are part of the same domain).

```python
{
    # Index of the validator whose key is being revealed
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
    # next_custody_reveal_period is initialized to the custody period
    # (of the particular validator) in which the validator is activated
    # = get_validators_custody_reveal_period(...)
    'next_custody_reveal_period': 'uint64',
    'max_reveal_lateness': 'uint64',
```

#### `BeaconState`

```python
    'custody_chunk_challenge_records': [CustodyChunkChallengeRecord],
    'custody_bit_challenge_records': [CustodyBitChallengeRecord],
    'custody_challenge_index': 'uint64',

    # Future derived secrets already exposed; contains the indices of the exposed validator
    # at RANDAO reveal period % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS
    'exposed_derived_secrets': [['uint64'], EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS],
```

#### `BeaconBlockBody`

```python
    'custody_chunk_challenges': [CustodyChunkChallenge],
    'custody_bit_challenges': [CustodyBitChallenge],
    'custody_responses': [CustodyResponse],
    'custody_key_reveals': [CustodyKeyReveal],
    'early_derived_secret_reveals': [EarlyDerivedSecretReveal],
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
    crosslink_crosslink_length = min(MAX_EPOCHS_PER_CROSSLINK, end_epoch - start_epoch)
    chunks_per_epoch = 2 * BYTES_PER_SHARD_BLOCK * SLOTS_PER_EPOCH // BYTES_PER_CUSTODY_CHUNK
    return crosslink_crosslink_length * chunks_per_epoch
```

### `get_custody_chunk_bit`

```python
def get_custody_chunk_bit(key: BLSSignature, chunk: bytes) -> bool:
    # TODO: Replace with something MPC-friendly, e.g. the Legendre symbol
    return get_bitfield_bit(hash(challenge.responder_key + chunk), 0)
```

### `get_chunk_bits_root`

```python
def get_chunk_bits_root(chunk_bitfield: Bitfield) -> Bytes32:
    aggregated_bits = bytearray([0] * 32)
    for i in range(0, len(chunk_bitfield), 32):
        for j in range(32):
            aggregated_bits[j] ^= chunk_bitfield[i+j]
    return hash(aggregated_bits)
```

### `get_randao_epoch_for_custody_period`

```python
def get_randao_epoch_for_custody_period(period: int, validator_index: ValidatorIndex) -> Epoch:
    next_period_start = (period + 1) * EPOCHS_PER_CUSTODY_PERIOD - validator_index % EPOCHS_PER_CUSTODY_PERIOD
    return next_period_start + CUSTODY_PERIOD_TO_RANDAO_PADDING
```

### `get_validators_custody_reveal_period`

 ```python
def get_validators_custody_reveal_period(state: BeaconState,
                                         validator_index: ValidatorIndex,
                                         epoch: Epoch=None) -> int:
    '''
    This function returns the reveal period for a given validator.
    If no epoch is supplied, the current epoch is assumed.
    Note: This function implicitly requires that validators are not removed from the
    validator set in fewer than EPOCHS_PER_CUSTODY_PERIOD epochs
    '''
    epoch = get_current_epoch(state) if epoch is None else epoch
    return (epoch + validator_index % EPOCHS_PER_CUSTODY_PERIOD) // EPOCHS_PER_CUSTODY_PERIOD
```

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

## Per-block processing

### Operations

Add the following operations to the per-block processing, in the order given below and after all other operations in Phase 0.

#### Custody key reveals

Verify that `len(block.body.custody_key_reveals) <= MAX_CUSTODY_KEY_REVEALS`.

For each `reveal` in `block.body.custody_key_reveals`, run the following function:

```python
def process_custody_key_reveal(state: BeaconState,
                           reveal: CustodyKeyReveal) -> None:

    """
    Process ``CustodyKeyReveal`` operation.
    Note that this function mutates ``state``.
    """

    revealer = state.validator_registry[reveal.revealer_index]
    epoch_to_sign = get_randao_epoch_for_custody_period(revealer.next_custody_reveal_period, reveal.revealed_index)

    assert revealer.next_custody_reveal_period < get_validators_custody_reveal_period(state, reveal.revealed_index)

    # Revealed validator is active or exited, but not withdrawn
    assert is_slashable_validator(revealer, get_current_epoch(state))

    # Verify signature
    assert bls_verify(
        pubkey=revealer.pubkey,
        message_hash=hash_tree_root(epoch_to_sign),
        signature=reveal.reveal,
        domain=get_domain(
            state=state,
            domain_type=DOMAIN_RANDAO,
            message_epoch=epoch_to_sign,
        ),
    )

    # Decrement max reveal lateness if response is timely
    if revealer.next_custody_reveal_period == get_validators_custody_reveal_period(state, reveal.revealer_index) - 2:
            revealer.max_reveal_lateness -=  MAX_REVEAL_LATENESS_DECREMENT
    revealer.max_reveal_lateness = max(revealed_validator.max_reveal_lateness, get_validators_custody_reveal_period(state, reveal.revealed_index) - revealer.next_custody_reveal_period)

    # Process reveal
    revealer.next_custody_reveal_period += 1

    # Reward Block Preposer
    proposer_index = get_beacon_proposer_index(state)
    increase_balance(state, proposer_index, base_reward(state, index) // MINOR_REWARD_QUOTIENT)
```

##### Early derived secret reveals

Verify that `len(block.body.early_derived_secret_reveals) <= MAX_EARLY_DERIVED_SECRET_REVEALS`.

For each `reveal` in `block.body.early_derived_secret_reveals`, run the following function:

```python
def process_early_derived_secret_reveal(state: BeaconState,
                              reveal: EarlyDerivedSecretReveal) -> None:
    """
    Process ``EarlyDerivedSecretReveal`` operation.
    Note that this function mutates ``state``.
    """

    revealed_validator = state.validator_registry[reveal.revealed_index]
    masker = state.validator_registry[reveal.masker_index]

    assert reveal.epoch >= get_current_epoch(state) + RANDAO_PENALTY_EPOCHS
    assert reveal.epoch < get_current_epoch(state) + EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS
    assert revealed_validator.slashed is False
    assert reveal.revealed_index not in state.exposed_derived_secrets[reveal.epoch % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS]

    # Verify signature correctness
    masker = state.validator_registry[reveal.masker_index]
    pubkeys = [revealed_validator.pubkey, masker.pubkey]
    message_hashes = [
        hash_tree_root(reveal.epoch),
        reveal.mask,
    ]

    assert bls_verify_multiple(
        pubkeys=pubkeys,
        message_hashes=message_hashes,
        signature=reveal.reveal,
        domain=get_domain(
            state=state,
            domain_type=DOMAIN_RANDAO,
            message_epoch=reveal.epoch,
        ),
    )

    if reveal.epoch >= get_current_epoch(state) + CUSTODY_PERIOD_TO_RANDAO_PADDING:
        # Full slashing when the secret was revealed so early it may be a valid custody
        # round key
        slash_validator(state, reveal.revealed_index, reveal.masker_index)
    else:
        # Only a small penalty proportional to proposer slot reward for RANDAO reveal
        # that does not interfere with the custody period
        # The penalty is proportional to the max proposer reward

        # Calculate penalty
        max_proposer_slot_reward = (
            get_base_reward(state, reveal.revealed_index) *
            SLOTS_PER_EPOCH //
            len(get_active_validator_indices(state, get_current_epoch(state))) //
            PROPOSER_REWARD_QUOTIENT
        )
        penalty = max_proposer_slot_reward * EARLY_DERIVED_SECRET_REVEAL_SLOT_REWARD_MULTIPLE * (len(state.exposed_derived_secrets[reveal.epoch % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS]) + 1)

        # Apply penalty
        proposer_index = get_beacon_proposer_index(state)
        whistleblower_index = reveal.masker_index
        whistleblowing_reward = penalty // WHISTLEBLOWING_REWARD_QUOTIENT
        proposer_reward = whistleblowing_reward // PROPOSER_REWARD_QUOTIENT
        increase_balance(state, proposer_index, proposer_reward)
        increase_balance(state, whistleblower_index, whistleblowing_reward - proposer_reward)
        decrease_balance(state, reveal.revealed_index, penalty)

        # Mark this derived secret as exposed so validator cannot be punished repeatedly
        state.exposed_derived_secrets[reveal.epoch % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS].append(reveal.revealed_index)

```

#### Chunk challenges

Verify that `len(block.body.custody_chunk_challenges) <= MAX_CUSTODY_CHUNK_CHALLENGES`.

For each `challenge` in `block.body.custody_chunk_challenges`, run the following function:

```python
def process_chunk_challenge(state: BeaconState,
                            challenge: CustodyChunkChallenge) -> None:
    # Verify the attestation
    assert verify_indexed_attestation(state, convert_to_indexed(state, challenge.attestation))
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
            record.data_root != challenge.attestation.data.crosslink.data_root or
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
        inclusion_epoch=get_current_epoch(state),
        data_root=challenge.attestation.data.crosslink.data_root,
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
    assert is_slashable_validator(challenger, get_current_epoch(state))

    # Verify the attestation
    assert verify_indexed_attestation(state, convert_to_indexed(state, challenge.attestation))
    # Verify the attestation is eligible for challenging
    responder = state.validator_registry[challenge.responder_index]
    assert (slot_to_epoch(challenge.attestation.data.slot) + responder.max_reveal_lateness <=
            get_validators_custody_reveal_period(state, challenge.responder_index))

    # Verify the responder participated in the attestation
    attesters = get_attesting_indices(state, attestation.data, attestation.aggregation_bitfield)
    assert challenge.responder_index in attesters

    # A validator can be the challenger for at most one challenge at a time
    for record in state.custody_bit_challenge_records:
        assert record.challenger_index != challenge.challenger_index

    # Verify the responder is a valid custody key
    epoch_to_sign = get_randao_epoch_for_custody_period(
        get_validators_custody_reveal_period(
            state=state,
            index=challenge.responder_index,
            epoch=slot_to_epoch(attestation.data.slot),
        challenge.responder_index
    )
    assert bls_verify(
        pubkey=responder.pubkey,
        message_hash=hash_tree_root(epoch_to_sign),
        signature=challenge.responder_key,
        domain=get_domain(
            state=state,
            domain_type=DOMAIN_RANDAO,
            message_epoch=epoch_to_sign,
        ),
    )

    # Verify the chunk count
    chunk_count = get_custody_chunk_count(challenge.attestation)
    assert verify_bitfield(challenge.chunk_bits, chunk_count)
    # Verify the first bit of the hash of the chunk bits does not equal the custody bit
    custody_bit = get_bitfield_bit(attestation.custody_bitfield, attesters.index(responder_index))
    assert custody_bit != get_bitfield_bit(get_chunk_bits_root(challenge.chunk_bits), 0)
    # Add new bit challenge record
    new_record = CustodyBitChallengeRecord(
        challenge_index=state.custody_challenge_index,
        challenger_index=challenge.challenger_index,
        responder_index=challenge.responder_index,
        inclusion_epoch=get_current_epoch(state),
        data_root=challenge.attestation.data.crosslink.data_root,
        chunk_count=chunk_count,
        chunk_bits_merkle_root=merkle_root(pad_to_power_of_2((challenge.chunk_bits))),
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
    # Verify bit challenge data is null
    assert response.chunk_bits_branch == [] and response.chunk_bits_leaf == ZERO_HASH
    # Verify minimum delay
    assert get_current_epoch(state) >= challenge.inclusion_epoch + ACTIVATION_EXIT_DELAY
    # Verify the chunk matches the crosslink data root
    assert verify_merkle_branch(
        leaf=hash_tree_root(response.chunk),
        branch=response.data_branch,
        depth=challenge.depth,
        index=response.chunk_index,
        root=challenge.data_root,
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
    assert response.chunk_index < challenge.chunk_count
    # Verify responder has not been slashed
    responder = state.validator_registry[challenge.responder_index]
    assert not responder.slashed
    # Verify the chunk matches the crosslink data root
    assert verify_merkle_branch(
        leaf=hash_tree_root(response.chunk),
        branch=response.data_branch,
        depth=math.log2(next_power_of_two(challenge.chunk_count)),
        index=response.chunk_index,
        root=challenge.data_root,
    )
    # Verify the chunk bit leaf matches the challenge data
    assert verify_merkle_branch(
        leaf=response.chunk_bits_leaf,
        branch=response.chunk_bits_branch,
        depth=math.log2(next_power_of_two(challenge.chunk_count) // 256),
        index=response.chunk_index // 256,
        root=challenge.chunk_bits_merkle_root
    )
    # Verify the chunk bit does not match the challenge chunk bit
    assert get_custody_chunk_bit(challenge.responder_key, response.chunk) != get_bitfield_bit(challenge.chunk_bits_leaf, response.chunk_index % 256)
    # Clear the challenge
    records = state.custody_bit_challenge_records
    records[records.index(challenge)] = CustodyBitChallengeRecord()
    # Slash challenger
    slash_validator(state, challenge.challenger_index, challenge.responder_index)
```

## Per-epoch processing

### Handling of custody-related deadlines

 Run `process_reveal_deadlines(state)` immediately after `process_ejections(state)`:

 ```python
def process_reveal_deadlines(state: BeaconState) -> None:
    for index, validator in enumerate(state.validator_registry):
        if (validator.latest_custody_reveal_period +
            (CUSTODY_RESPONSE_DEADLINE // EPOCHS_PER_CUSTODY_PERIOD) <
            get_validators_custody_reveal_period(state, index)):
                slash_validator(state, index)
```

Run `process_challenge_deadlines(state)` immediately after `process_reveal_deadlines(state)`:

```python
def process_challenge_deadlines(state: BeaconState) -> None:
    for challenge in state.custody_chunk_challenge_records:
        if get_current_epoch(state) > challenge.inclusion_epoch + CUSTODY_RESPONSE_DEADLINE:
            slash_validator(state, challenge.responder_index, challenge.challenger_index)
            records = state.custody_chunk_challenge_records
            records[records.index(challenge)] = CustodyChunkChallengeRecord()

    for challenge in state.custody_bit_challenge_records:
        if get_current_epoch(state) > challenge.inclusion_epoch + CUSTODY_RESPONSE_DEADLINE:
            slash_validator(state, challenge.responder_index, challenge.challenger_index)
            records = state.custody_bit_challenge_records
            records[records.index(challenge)] = CustodyBitChallengeRecord()
```

Append this to `process_final_updates(state)`:

```python
    # Clean up exposed RANDAO key reveals
    state.exposed_derived_secrets[current_epoch % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS] = []
    # Reset withdrawable epochs if challenge records are empty
    records = state.custody_chunk_challenge_records + state.bit_challenge_records
    validator_indices_in_records = set(
        [record.challenger_index for record in records] + [record.responder_index for record in records]
    )
    for index, validator in enumerate(state.validator_registry):
        if index not in validator_indices_in_records:
            if validator.exit_epoch != FAR_FUTURE_EPOCH and validator.withdrawable_epoch == FAR_FUTURE_EPOCH:
                validator.withdrawable_epoch = validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
```

In `process_penalties_and_exits`, change the definition of `eligible` to the following (note that it is not a pure function because `state` is declared in the surrounding scope):

```python
def eligible(state: BeaconState, index: ValidatorIndex) -> bool:
    validator = state.validator_registry[index]
    # Cannot exit if there are still open chunk challenges
    if len([record for record in state.custody_chunk_challenge_records if record.responder_index == index]) > 0:
        return False
    # Cannot exit if there are still open bit challenges
    if len([record for record in state.custody_bit_challenge_records if record.responder_index == index]) > 0:
        return False
    # Cannot exit if you have not revealed all of your custody keys
    elif validator.next_custody_reveal_period <= get_validators_custody_reveal_period(state, index, validator.exit_epoch):
        return False
    # Cannot exit if you already have
    elif validator.withdrawable_epoch < FAR_FUTURE_EPOCH:
        return False
    # Return minimum time
    else:
        return current_epoch >= validator.exit_epoch + MIN_VALIDATOR_WITHDRAWAL_EPOCHS
```
