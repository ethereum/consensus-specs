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
        - [Custody game parameters](#custody-game-parameters)
        - [Time parameters](#time-parameters)
        - [Max operations per block](#max-operations-per-block)
        - [Reward and penalty quotients](#reward-and-penalty-quotients)
        - [Signature domain types](#signature-domain-types)
        - [TODO PLACEHOLDER](#todo-placeholder)
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
        - [`ceillog2`](#ceillog2)
        - [`is_valid_merkle_branch_with_mixin`](#is_valid_merkle_branch_with_mixin)
        - [`get_crosslink_chunk_count`](#get_crosslink_chunk_count)
        - [`legendre_bit`](#legendre_bit)
        - [`custody_subchunkify`](#custody_subchunkify)
        - [`get_custody_chunk_bit`](#get_custody_chunk_bit)
        - [`get_chunk_bits_root`](#get_chunk_bits_root)
        - [`get_randao_epoch_for_custody_period`](#get_randao_epoch_for_custody_period)
        - [`get_custody_period_for_validator`](#get_custody_period_for_validator)
        - [`replace_empty_or_append`](#replace_empty_or_append)
    - [Per-block processing](#per-block-processing)
        - [Operations](#operations)
            - [Custody key reveals](#custody-key-reveals)
            - [Early derived secret reveals](#early-derived-secret-reveals)
            - [Chunk challenges](#chunk-challenges)
            - [Bit challenges](#bit-challenges)
            - [Custody responses](#custody-responses)
    - [Per-epoch processing](#per-epoch-processing)
        - [Handling of custody-related deadlines](#handling-of-custody-related-deadlines)

<!-- /TOC -->

## Introduction

This document details the beacon chain additions and changes in Phase 1 of Ethereum 2.0 to support the shard data custody game, building upon the [Phase 0](0_beacon-chain.md) specification.

## Terminology

- **Custody game**—
- **Custody period**—
- **Custody chunk**—
- **Custody chunk bit**—
- **Custody chunk challenge**—
- **Custody bit**—
- **Custody bit challenge**—
- **Custody key**—
- **Custody key reveal**—
- **Custody key mask**—
- **Custody response**—
- **Custody response deadline**—

## Constants

### Misc
| Name | Value |
| - | - |
| `BLS12_381_Q` | `4002409555221667393417789825735904156556882819939007885332058136124031650490837864442687629129015664037894272559787` |
| `MINOR_REWARD_QUOTIENT` | `2**8` (= 256) |
| `MAX_EPOCHS_PER_CROSSLINK` | `2**6` (= 64) | epochs | ~7 hours |

### Custody game parameters

| Name | Value |
| - | - |
| `BYTES_PER_SHARD_BLOCK` | `2**14` (= 16,384) |
| `BYTES_PER_CUSTODY_CHUNK` | `2**9` (= 512) |
| `BYTES_PER_CUSTODY_SUBCHUNK` | `48` |
| `CHUNKS_PER_EPOCH` | `2 * BYTES_PER_SHARD_BLOCK * SLOTS_PER_EPOCH // BYTES_PER_CUSTODY_CHUNK` |
| `MAX_CUSTODY_CHUNKS` | `MAX_EPOCHS_PER_CROSSLINK * CHUNKS_PER_EPOCH` |
| `CUSTODY_DATA_DEPTH` | `ceillog2(MAX_CUSTODY_CHUNKS) + 1` |
| `CUSTODY_CHUNK_BIT_DEPTH` | `ceillog2(MAX_EPOCHS_PER_CROSSLINK * CHUNKS_PER_EPOCH // 256) + 2` |

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

| Name | Value |
| - | - |
| `EARLY_DERIVED_SECRET_REVEAL_SLOT_REWARD_MULTIPLE` | `2**1` (= 2) |

### Signature domain types

The following types are defined, mapping into `DomainType` (little endian):

| Name | Value |
| - | - |
| `DOMAIN_CUSTODY_BIT_CHALLENGE` | `6` |

### TODO PLACEHOLDER

| Name | Value |
| - | - |
| `PLACEHOLDER` | `2**32` |

## Data structures

### Custody objects

#### `CustodyChunkChallenge`

```python
class CustodyChunkChallenge(Container):
    responder_index: ValidatorIndex
    attestation: Attestation
    chunk_index: uint64
```

#### `CustodyBitChallenge`

```python
class CustodyBitChallenge(Container):
    responder_index: ValidatorIndex
    attestation: Attestation
    challenger_index: ValidatorIndex
    responder_key: BLSSignature
    chunk_bits: Bitlist[MAX_CUSTODY_CHUNKS]
    signature: BLSSignature
```

#### `CustodyChunkChallengeRecord`

```python
class CustodyChunkChallengeRecord(Container):
    challenge_index: uint64
    challenger_index: ValidatorIndex
    responder_index: ValidatorIndex
    inclusion_epoch: Epoch
    data_root: Root
    depth: uint64
    chunk_index: uint64
```

#### `CustodyBitChallengeRecord`

```python
class CustodyBitChallengeRecord(Container):
    challenge_index: uint64
    challenger_index: ValidatorIndex
    responder_index: ValidatorIndex
    inclusion_epoch: Epoch
    data_root: Root
    chunk_count: uint64
    chunk_bits_merkle_root: Root
    responder_key: BLSSignature
```

#### `CustodyResponse`

```python
class CustodyResponse(Container):
    challenge_index: uint64
    chunk_index: uint64
    chunk: BytesN[BYTES_PER_CUSTODY_CHUNK]
    data_branch: List[Bytes32, CUSTODY_DATA_DEPTH]
    chunk_bits_branch: List[Bytes32, CUSTODY_CHUNK_BIT_DEPTH]
    chunk_bits_leaf: Bitvector[256]
```

### New beacon operations

#### `CustodyKeyReveal`

```python
class CustodyKeyReveal(Container):
    # Index of the validator whose key is being revealed
    revealer_index: ValidatorIndex
    # Reveal (masked signature)
    reveal: BLSSignature
```

#### `EarlyDerivedSecretReveal`

Represents an early (punishable) reveal of one of the derived secrets, where derived secrets are RANDAO reveals and custody reveals (both are part of the same domain).

```python
class EarlyDerivedSecretReveal(Container):
    # Index of the validator whose key is being revealed
    revealed_index: ValidatorIndex
    # RANDAO epoch of the key that is being revealed
    epoch: Epoch
    # Reveal (masked signature)
    reveal: BLSSignature
    # Index of the validator who revealed (whistleblower)
    masker_index: ValidatorIndex
    # Mask used to hide the actual reveal signature (prevent reveal from being stolen)
    mask: Bytes32
```

### Phase 0 container updates

Add the following fields to the end of the specified container objects. Fields with underlying type `uint64` are initialized to `0` and list fields are initialized to `[]`.

#### `Validator`

```python
class Validator(Container):
    # next_custody_secret_to_reveal is initialised to the custody period
    # (of the particular validator) in which the validator is activated
    # = get_custody_period_for_validator(...)
    next_custody_secret_to_reveal: uint64
    max_reveal_lateness: Epoch
```

#### `BeaconState`

```python
class BeaconState(Container):
    custody_chunk_challenge_records: List[CustodyChunkChallengeRecord, PLACEHOLDER]
    custody_bit_challenge_records: List[CustodyBitChallengeRecord, PLACEHOLDER]
    custody_challenge_index: uint64

    # Future derived secrets already exposed; contains the indices of the exposed validator
    # at RANDAO reveal period % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS
    exposed_derived_secrets: Vector[List[ValidatorIndex, PLACEHOLDER],
                                    EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS]
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    custody_chunk_challenges: List[CustodyChunkChallenge, PLACEHOLDER]
    custody_bit_challenges: List[CustodyBitChallenge, PLACEHOLDER]
    custody_responses: List[CustodyResponse, PLACEHOLDER]
    custody_key_reveals: List[CustodyKeyReveal, PLACEHOLDER]
    early_derived_secret_reveals: List[EarlyDerivedSecretReveal, PLACEHOLDER]
```

## Helpers

### `ceillog2`

```python
def ceillog2(x: uint64) -> int:
    return (x - 1).bit_length()
```

### `is_valid_merkle_branch_with_mixin`

```python
def is_valid_merkle_branch_with_mixin(leaf: Bytes32,
                                      branch: Sequence[Bytes32],
                                      depth: uint64,
                                      index: uint64,
                                      root: Root,
                                      mixin: uint64) -> bool:
    value = leaf
    for i in range(depth):
        if index // (2**i) % 2:
            value = hash(branch[i] + value)
        else:
            value = hash(value + branch[i])
    value = hash(value + mixin.to_bytes(32, "little"))
    return value == root
```

### `get_crosslink_chunk_count`

```python
def get_custody_chunk_count(crosslink: Crosslink) -> int:
    crosslink_length = min(MAX_EPOCHS_PER_CROSSLINK, crosslink.end_epoch - crosslink.start_epoch)
    return crosslink_length * CHUNKS_PER_EPOCH
```

### `legendre_bit`

Returns the Legendre symbol `(a/q)` normalizes as a bit (i.e. `((a/q) + 1) // 2`). In a production implementation, a well-optimized library (e.g. GMP) should be used for this.

```python
def legendre_bit(a: int, q: int) -> int:
    if a >= q:
        return legendre_bit(a % q, q)
    if a == 0:
        return 0
    assert(q > a > 0 and q % 2 == 1)
    t = 1
    n = q
    while a != 0:
        while a % 2 == 0:
            a //= 2
            r = n % 8
            if r == 3 or r == 5:
                t = -t
        a, n = n, a
        if a % 4 == n % 4 == 3:
            t = -t
        a %= n
    if n == 1:
        return (t + 1) // 2
    else:
        return 0
```

### `custody_subchunkify`

Given one proof of custody chunk, returns the proof of custody subchunks of the correct sizes.

```python
def custody_subchunkify(bytez: bytes) -> Sequence[bytes]:
    bytez += b'\x00' * (-len(bytez) % BYTES_PER_CUSTODY_SUBCHUNK)
    return [bytez[i:i + BYTES_PER_CUSTODY_SUBCHUNK]
            for i in range(0, len(bytez), BYTES_PER_CUSTODY_SUBCHUNK)]
```

### `get_custody_chunk_bit`

```python
def get_custody_chunk_bit(key: BLSSignature, chunk: bytes) -> bool:
    full_G2_element = bls_signature_to_G2(key)
    s = full_G2_element[0].coeffs
    bits = [legendre_bit((i + 1) * s[i % 2] + int.from_bytes(subchunk, "little"), BLS12_381_Q)
            for i, subchunk in enumerate(custody_subchunkify(chunk))]

    return bool(sum(bits) % 2)
```

### `get_chunk_bits_root`

```python
def get_chunk_bits_root(chunk_bits: Bitlist[MAX_CUSTODY_CHUNKS]) -> bit:
    aggregated_bits = 0
    for i, b in enumerate(chunk_bits):
        aggregated_bits += 2**i * b
    return legendre_bit(aggregated_bits, BLS12_381_Q)
```

### `get_randao_epoch_for_custody_period`

```python
def get_randao_epoch_for_custody_period(period: uint64, validator_index: ValidatorIndex) -> Epoch:
    next_period_start = (period + 1) * EPOCHS_PER_CUSTODY_PERIOD - validator_index % EPOCHS_PER_CUSTODY_PERIOD
    return Epoch(next_period_start + CUSTODY_PERIOD_TO_RANDAO_PADDING)
```

### `get_custody_period_for_validator`

```python
def get_custody_period_for_validator(state: BeaconState, validator_index: ValidatorIndex, epoch: Epoch=None) -> int:
    '''
    Return the reveal period for a given validator.
    '''
    epoch = get_current_epoch(state) if epoch is None else epoch
    return (epoch + validator_index % EPOCHS_PER_CUSTODY_PERIOD) // EPOCHS_PER_CUSTODY_PERIOD
```

### `replace_empty_or_append`

```python
def replace_empty_or_append(list: MutableSequence[Any], new_element: Any) -> int:
    for i in range(len(list)):
        if is_zero(list[i]):
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
def process_custody_key_reveal(state: BeaconState, reveal: CustodyKeyReveal) -> None:
    """
    Process ``CustodyKeyReveal`` operation.
    Note that this function mutates ``state``.
    """
    revealer = state.validators[reveal.revealer_index]
    epoch_to_sign = get_randao_epoch_for_custody_period(revealer.next_custody_secret_to_reveal, reveal.revealer_index)

    assert revealer.next_custody_secret_to_reveal < get_custody_period_for_validator(state, reveal.revealer_index)

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
    if epoch_to_sign + EPOCHS_PER_CUSTODY_PERIOD >= get_current_epoch(state):
        if revealer.max_reveal_lateness >= MAX_REVEAL_LATENESS_DECREMENT:
            revealer.max_reveal_lateness -= MAX_REVEAL_LATENESS_DECREMENT
        else:
            revealer.max_reveal_lateness = 0
    else:
        revealer.max_reveal_lateness = max(
            revealer.max_reveal_lateness,
            get_current_epoch(state) - epoch_to_sign - EPOCHS_PER_CUSTODY_PERIOD
        )

    # Process reveal
    revealer.next_custody_secret_to_reveal += 1

    # Reward Block Preposer
    proposer_index = get_beacon_proposer_index(state)
    increase_balance(
        state,
        proposer_index,
        Gwei(get_base_reward(state, reveal.revealer_index) // MINOR_REWARD_QUOTIENT)
    )
```

#### Early derived secret reveals

Verify that `len(block.body.early_derived_secret_reveals) <= MAX_EARLY_DERIVED_SECRET_REVEALS`.

For each `reveal` in `block.body.early_derived_secret_reveals`, run the following function:

```python
def process_early_derived_secret_reveal(state: BeaconState, reveal: EarlyDerivedSecretReveal) -> None:
    """
    Process ``EarlyDerivedSecretReveal`` operation.
    Note that this function mutates ``state``.
    """
    revealed_validator = state.validators[reveal.revealed_index]
    derived_secret_location = reveal.epoch % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS

    assert reveal.epoch >= get_current_epoch(state) + RANDAO_PENALTY_EPOCHS
    assert reveal.epoch < get_current_epoch(state) + EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS
    assert not revealed_validator.slashed
    assert reveal.revealed_index not in state.exposed_derived_secrets[derived_secret_location]

    # Verify signature correctness
    masker = state.validators[reveal.masker_index]
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
            get_base_reward(state, reveal.revealed_index)
            * SLOTS_PER_EPOCH
            // len(get_active_validator_indices(state, get_current_epoch(state)))
            // PROPOSER_REWARD_QUOTIENT
        )
        penalty = Gwei(
            max_proposer_slot_reward
            * EARLY_DERIVED_SECRET_REVEAL_SLOT_REWARD_MULTIPLE
            * (len(state.exposed_derived_secrets[derived_secret_location]) + 1)
        )

        # Apply penalty
        proposer_index = get_beacon_proposer_index(state)
        whistleblower_index = reveal.masker_index
        whistleblowing_reward = Gwei(penalty // WHISTLEBLOWER_REWARD_QUOTIENT)
        proposer_reward = Gwei(whistleblowing_reward // PROPOSER_REWARD_QUOTIENT)
        increase_balance(state, proposer_index, proposer_reward)
        increase_balance(state, whistleblower_index, whistleblowing_reward - proposer_reward)
        decrease_balance(state, reveal.revealed_index, penalty)

        # Mark this derived secret as exposed so validator cannot be punished repeatedly
        state.exposed_derived_secrets[derived_secret_location].append(reveal.revealed_index)
```

#### Chunk challenges

Verify that `len(block.body.custody_chunk_challenges) <= MAX_CUSTODY_CHUNK_CHALLENGES`.

For each `challenge` in `block.body.custody_chunk_challenges`, run the following function:

```python
def process_chunk_challenge(state: BeaconState, challenge: CustodyChunkChallenge) -> None:
    # Verify the attestation
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, challenge.attestation))
    # Verify it is not too late to challenge
    assert (compute_epoch_at_slot(challenge.attestation.data.slot)
            >= get_current_epoch(state) - MAX_CHUNK_CHALLENGE_DELAY)
    responder = state.validators[challenge.responder_index]
    assert responder.exit_epoch >= get_current_epoch(state) - MAX_CHUNK_CHALLENGE_DELAY
    # Verify the responder participated in the attestation
    attesters = get_attesting_indices(state, challenge.attestation.data, challenge.attestation.aggregation_bits)
    assert challenge.responder_index in attesters
    # Verify the challenge is not a duplicate
    for record in state.custody_chunk_challenge_records:
        assert (
            record.data_root != challenge.attestation.data.crosslink.data_root or
            record.chunk_index != challenge.chunk_index
        )
    # Verify depth
    depth = ceillog2(get_custody_chunk_count(challenge.attestation.data.crosslink))
    assert challenge.chunk_index < 2**depth
    # Add new chunk challenge record
    new_record = CustodyChunkChallengeRecord(
        challenge_index=state.custody_challenge_index,
        challenger_index=get_beacon_proposer_index(state),
        responder_index=challenge.responder_index,
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
def process_bit_challenge(state: BeaconState, challenge: CustodyBitChallenge) -> None:
    attestation = challenge.attestation
    epoch = attestation.data.target.epoch
    shard = attestation.data.crosslink.shard

    # Verify challenge signature
    challenger = state.validators[challenge.challenger_index]
    domain = get_domain(state, DOMAIN_CUSTODY_BIT_CHALLENGE, get_current_epoch(state))
    assert bls_verify(challenger.pubkey, signing_root(challenge), challenge.signature, domain)
    # Verify challenger is slashable
    assert is_slashable_validator(challenger, get_current_epoch(state))
    # Verify attestation
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))
    # Verify attestation is eligible for challenging
    responder = state.validators[challenge.responder_index]
    assert get_current_epoch(state) <= get_randao_epoch_for_custody_period(
        get_custody_period_for_validator(state, challenge.responder_index, epoch),
        challenge.responder_index
    ) + 2 * EPOCHS_PER_CUSTODY_PERIOD + responder.max_reveal_lateness

    # Verify the responder participated in the attestation
    attesters = get_attesting_indices(state, attestation.data, attestation.aggregation_bits)
    assert challenge.responder_index in attesters
    # Verifier challenger is not already challenging
    for record in state.custody_bit_challenge_records:
        assert record.challenger_index != challenge.challenger_index
    # Verify the responder custody key
    epoch_to_sign = get_randao_epoch_for_custody_period(
        get_custody_period_for_validator(state, challenge.responder_index, epoch),
        challenge.responder_index,
    )
    domain = get_domain(state, DOMAIN_RANDAO, epoch_to_sign)
    assert bls_verify(responder.pubkey, hash_tree_root(epoch_to_sign), challenge.responder_key, domain)
    # Verify the chunk count
    chunk_count = get_custody_chunk_count(attestation.data.crosslink)
    assert chunk_count == len(challenge.chunk_bits)
    # Verify custody bit is incorrect
    committee = get_beacon_committee(state, epoch, shard)
    custody_bit = attestation.custody_bits[committee.index(challenge.responder_index)]
    assert custody_bit != get_chunk_bits_root(challenge.chunk_bits)
    # Add new bit challenge record
    new_record = CustodyBitChallengeRecord(
        challenge_index=state.custody_challenge_index,
        challenger_index=challenge.challenger_index,
        responder_index=challenge.responder_index,
        inclusion_epoch=get_current_epoch(state),
        data_root=attestation.data.crosslink.data_root,
        chunk_count=chunk_count,
        chunk_bits_merkle_root=hash_tree_root(challenge.chunk_bits),
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
def process_custody_response(state: BeaconState, response: CustodyResponse) -> None:
    chunk_challenge = next((record for record in state.custody_chunk_challenge_records
                            if record.challenge_index == response.challenge_index), None)
    if chunk_challenge is not None:
        return process_chunk_challenge_response(state, response, chunk_challenge)

    bit_challenge = next((record for record in state.custody_bit_challenge_records
                          if record.challenge_index == response.challenge_index), None)
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
    assert response.chunk_bits_branch == [] and response.chunk_bits_leaf == Bytes32()
    # Verify minimum delay
    assert get_current_epoch(state) >= challenge.inclusion_epoch + MAX_SEED_LOOKAHEAD
    # Verify the chunk matches the crosslink data root
    assert is_valid_merkle_branch(
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
    increase_balance(state, proposer_index, Gwei(get_base_reward(state, proposer_index) // MINOR_REWARD_QUOTIENT))
```

```python
def process_bit_challenge_response(state: BeaconState,
                                   response: CustodyResponse,
                                   challenge: CustodyBitChallengeRecord) -> None:
    # Verify chunk index
    assert response.chunk_index < challenge.chunk_count
    # Verify responder has not been slashed
    responder = state.validators[challenge.responder_index]
    assert not responder.slashed
    # Verify the chunk matches the crosslink data root
    assert is_valid_merkle_branch(
        leaf=hash_tree_root(response.chunk),
        branch=response.data_branch,
        depth=ceillog2(challenge.chunk_count),
        index=response.chunk_index,
        root=challenge.data_root,
    )
    # Verify the chunk bit leaf matches the challenge data
    assert is_valid_merkle_branch_with_mixin(
        leaf=hash_tree_root(response.chunk_bits_leaf),
        branch=response.chunk_bits_branch,
        depth=ceillog2(MAX_CUSTODY_CHUNKS // 256),
        index=response.chunk_index // 256,
        root=challenge.chunk_bits_merkle_root,
        mixin=challenge.chunk_count,
    )
    # Verify the chunk bit does not match the challenge chunk bit
    assert (get_custody_chunk_bit(challenge.responder_key, response.chunk)
            != response.chunk_bits_leaf[response.chunk_index % 256])
    # Clear the challenge
    records = state.custody_bit_challenge_records
    records[records.index(challenge)] = CustodyBitChallengeRecord()
    # Slash challenger
    slash_validator(state, challenge.challenger_index, challenge.responder_index)
```

## Per-epoch processing

### Handling of custody-related deadlines

Run `process_reveal_deadlines(state)` immediately after `process_registry_updates(state)`:

```python
# begin insert @process_reveal_deadlines
    process_reveal_deadlines(state)
# end insert @process_reveal_deadlines
def process_reveal_deadlines(state: BeaconState) -> None:
    for index, validator in enumerate(state.validators):
        deadline = validator.next_custody_secret_to_reveal + (CUSTODY_RESPONSE_DEADLINE // EPOCHS_PER_CUSTODY_PERIOD)
        if get_custody_period_for_validator(state, ValidatorIndex(index)) > deadline:
            slash_validator(state, ValidatorIndex(index))
```

Run `process_challenge_deadlines(state)` immediately after `process_reveal_deadlines(state)`:

```python
# begin insert @process_challenge_deadlines
    process_challenge_deadlines(state)
# end insert @process_challenge_deadlines
def process_challenge_deadlines(state: BeaconState) -> None:
    for custody_chunk_challenge in state.custody_chunk_challenge_records:
        if get_current_epoch(state) > custody_chunk_challenge.inclusion_epoch + CUSTODY_RESPONSE_DEADLINE:
            slash_validator(state, custody_chunk_challenge.responder_index, custody_chunk_challenge.challenger_index)
            records = state.custody_chunk_challenge
            records[records.index(custody_chunk_challenge)] = CustodyChunkChallengeRecord()

    for custody_bit_challenge in state.custody_bit_challenge_records:
        if get_current_epoch(state) > custody_bit_challenge.inclusion_epoch + CUSTODY_RESPONSE_DEADLINE:
            slash_validator(state, custody_bit_challenge.responder_index, custody_bit_challenge.challenger_index)
            records = state.custody_bit_challenge_records
            records[records.index(custody_bit_challenge)] = CustodyBitChallengeRecord()
```

Append this to `process_final_updates(state)`:

```python
# begin insert @after_process_final_updates
    after_process_final_updates(state)
# end insert @after_process_final_updates
def after_process_final_updates(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    # Clean up exposed RANDAO key reveals
    state.exposed_derived_secrets[current_epoch % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS] = []
    # Reset withdrawable epochs if challenge records are empty
    records = state.custody_chunk_challenge_records + state.custody_bit_challenge_records
    validator_indices_in_records = set(
        [record.challenger_index for record in records] + [record.responder_index for record in records]
    )
    for index, validator in enumerate(state.validators):
        if index not in validator_indices_in_records:
            if validator.exit_epoch != FAR_FUTURE_EPOCH and validator.withdrawable_epoch == FAR_FUTURE_EPOCH:
                validator.withdrawable_epoch = Epoch(validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY)
```
