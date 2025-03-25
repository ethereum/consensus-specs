# Custody Game -- The Beacon Chain

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Misc](#misc)
  - [Domain types](#domain-types)
- [Preset](#preset)
  - [Time parameters](#time-parameters)
  - [Max operations per block](#max-operations-per-block)
  - [Size parameters](#size-parameters)
  - [Reward and penalty quotients](#reward-and-penalty-quotients)
- [Data structures](#data-structures)
  - [Extended types](#extended-types)
    - [`Validator`](#validator)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
  - [New Beacon Chain operations](#new-beacon-chain-operations)
    - [`CustodyChunkChallenge`](#custodychunkchallenge)
    - [`CustodyChunkChallengeRecord`](#custodychunkchallengerecord)
    - [`CustodyChunkResponse`](#custodychunkresponse)
    - [`CustodySlashing`](#custodyslashing)
    - [`SignedCustodySlashing`](#signedcustodyslashing)
    - [`CustodyKeyReveal`](#custodykeyreveal)
    - [`EarlyDerivedSecretReveal`](#earlyderivedsecretreveal)
- [Helpers](#helpers)
  - [`replace_empty_or_append`](#replace_empty_or_append)
  - [`legendre_bit`](#legendre_bit)
  - [`get_custody_atoms`](#get_custody_atoms)
  - [`get_custody_secrets`](#get_custody_secrets)
  - [`universal_hash_function`](#universal_hash_function)
  - [`compute_custody_bit`](#compute_custody_bit)
  - [`get_randao_epoch_for_custody_period`](#get_randao_epoch_for_custody_period)
  - [`get_custody_period_for_validator`](#get_custody_period_for_validator)
- [Per-block processing](#per-block-processing)
  - [Block processing](#block-processing)
  - [Custody Game Operations](#custody-game-operations)
    - [Chunk challenges](#chunk-challenges)
    - [Custody chunk response](#custody-chunk-response)
    - [Custody key reveals](#custody-key-reveals)
    - [Early derived secret reveals](#early-derived-secret-reveals)
    - [Custody Slashings](#custody-slashings)
- [Per-epoch processing](#per-epoch-processing)
  - [Epoch transition](#epoch-transition)
  - [Handling of reveal deadlines](#handling-of-reveal-deadlines)
  - [Final updates](#final-updates)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document details the beacon chain additions and changes of to support the shard data custody game,
building upon the [Sharding](../sharding/beacon-chain.md) specification.

## Constants

### Misc

| Name | Value | Unit |
| - | - | - |
| `CUSTODY_PRIME` | `int(2 ** 256 - 189)` | - |
| `CUSTODY_SECRETS` | `uint64(3)` | - |
| `BYTES_PER_CUSTODY_ATOM` | `uint64(32)` | bytes |
| `CUSTODY_PROBABILITY_EXPONENT` | `uint64(10)` | - |

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_CUSTODY_BIT_SLASHING` | `DomainType('0x83000000')` |

## Preset

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `RANDAO_PENALTY_EPOCHS` | `uint64(2**1)` (= 2) | epochs | 12.8 minutes |
| `EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS` | `uint64(2**15)` (= 32,768) | epochs | ~146 days |
| `EPOCHS_PER_CUSTODY_PERIOD` | `uint64(2**14)` (= 16,384) | epochs | ~73 days |
| `CUSTODY_PERIOD_TO_RANDAO_PADDING` | `uint64(2**11)` (= 2,048) | epochs | ~9 days |
| `MAX_CHUNK_CHALLENGE_DELAY` | `uint64(2**15)` (= 32,768) | epochs | ~146 days |

### Max operations per block

| Name | Value |
| - | - |
| `MAX_CUSTODY_CHUNK_CHALLENGE_RECORDS` | `uint64(2**20)` (= 1,048,576) |
| `MAX_CUSTODY_KEY_REVEALS` | `uint64(2**8)` (= 256) |
| `MAX_EARLY_DERIVED_SECRET_REVEALS` | `uint64(2**0)` (= 1) |
| `MAX_CUSTODY_CHUNK_CHALLENGES` | `uint64(2**2)` (= 4) |
| `MAX_CUSTODY_CHUNK_CHALLENGE_RESPONSES` | `uint64(2**4)` (= 16) |
| `MAX_CUSTODY_SLASHINGS` | `uint64(2**0)` (= 1) |

### Size parameters

| Name | Value | Unit |
| - | - | - |
| `BYTES_PER_CUSTODY_CHUNK` | `uint64(2**12)` (= 4,096) | bytes |
| `CUSTODY_RESPONSE_DEPTH` | `ceillog2(MAX_SHARD_BLOCK_SIZE // BYTES_PER_CUSTODY_CHUNK)` | - |

### Reward and penalty quotients

| Name | Value |
| - | - |
| `EARLY_DERIVED_SECRET_REVEAL_SLOT_REWARD_MULTIPLE` | `uint64(2**1)` (= 2) |
| `MINOR_REWARD_QUOTIENT` | `uint64(2**8)` (= 256) |

## Data structures

### Extended types

#### `Validator`

```python
class Validator(sharding.Validator):
    # next_custody_secret_to_reveal is initialised to the custody period
    # (of the particular validator) in which the validator is activated
    # = get_custody_period_for_validator(...)
    next_custody_secret_to_reveal: uint64
    # TODO: The max_reveal_lateness doesn't really make sense anymore.
    # So how do we incentivise early custody key reveals now?
    all_custody_secrets_revealed_epoch: Epoch  # to be initialized to FAR_FUTURE_EPOCH
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(sharding.BeaconBlockBody):
    # Custody game
    chunk_challenges: List[CustodyChunkChallenge, MAX_CUSTODY_CHUNK_CHALLENGES]
    chunk_challenge_responses: List[
        CustodyChunkResponse, MAX_CUSTODY_CHUNK_CHALLENGE_RESPONSES
    ]
    custody_key_reveals: List[CustodyKeyReveal, MAX_CUSTODY_KEY_REVEALS]
    early_derived_secret_reveals: List[
        EarlyDerivedSecretReveal, MAX_EARLY_DERIVED_SECRET_REVEALS
    ]
    custody_slashings: List[SignedCustodySlashing, MAX_CUSTODY_SLASHINGS]
```

#### `BeaconState`

```python
class BeaconState(sharding.BeaconState):
    # Future derived secrets already exposed; contains the indices of the exposed validator
    # at RANDAO reveal period % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS
    exposed_derived_secrets: Vector[
        List[ValidatorIndex, MAX_EARLY_DERIVED_SECRET_REVEALS * SLOTS_PER_EPOCH],
        EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS,
    ]
    custody_chunk_challenge_records: List[
        CustodyChunkChallengeRecord, MAX_CUSTODY_CHUNK_CHALLENGE_RECORDS
    ]
    custody_chunk_challenge_index: uint64
```

### New Beacon Chain operations

#### `CustodyChunkChallenge`

```python
class CustodyChunkChallenge(Container):
    responder_index: ValidatorIndex
    shard_transition: ShardTransition
    attestation: Attestation
    data_index: uint64
    chunk_index: uint64
```

#### `CustodyChunkChallengeRecord`

```python
class CustodyChunkChallengeRecord(Container):
    challenge_index: uint64
    challenger_index: ValidatorIndex
    responder_index: ValidatorIndex
    inclusion_epoch: Epoch
    data_root: Root
    chunk_index: uint64
```

#### `CustodyChunkResponse`

```python
class CustodyChunkResponse(Container):
    challenge_index: uint64
    chunk_index: uint64
    chunk: ByteVector[BYTES_PER_CUSTODY_CHUNK]
    branch: Vector[Root, CUSTODY_RESPONSE_DEPTH + 1]
```

#### `CustodySlashing`

```python
class CustodySlashing(Container):
    # (Attestation.data.shard_transition_root as ShardTransition).shard_data_roots[data_index] is the root of the data.
    data_index: uint64
    malefactor_index: ValidatorIndex
    malefactor_secret: BLSSignature
    whistleblower_index: ValidatorIndex
    shard_transition: ShardTransition
    attestation: Attestation
    data: ByteList[MAX_SHARD_BLOCK_SIZE]
```

#### `SignedCustodySlashing`

```python
class SignedCustodySlashing(Container):
    message: CustodySlashing
    signature: BLSSignature
```

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

## Helpers

### `replace_empty_or_append`

```python
def replace_empty_or_append(l: List, new_element: Any) -> int:
    for i in range(len(l)):
        if l[i] == type(new_element)():
            l[i] = new_element
            return i
    l.append(new_element)
    return len(l) - 1
```

### `legendre_bit`

Returns the Legendre symbol `(a/q)` normalizes as a bit (i.e. `((a/q) + 1) // 2`). In a production implementation, a well-optimized library (e.g. GMP) should be used for this.

```python
def legendre_bit(a: int, q: int) -> int:
    if a >= q:
        return legendre_bit(a % q, q)
    if a == 0:
        return 0
    assert q > a > 0 and q % 2 == 1
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

### `get_custody_atoms`

Given one set of data, return the custody atoms: each atom will be combined with one legendre bit.

```python
def get_custody_atoms(bytez: bytes) -> Sequence[bytes]:
    length_remainder = len(bytez) % BYTES_PER_CUSTODY_ATOM
    bytez += b"\x00" * (
        (BYTES_PER_CUSTODY_ATOM - length_remainder) % BYTES_PER_CUSTODY_ATOM
    )  # right-padding
    return [
        bytez[i : i + BYTES_PER_CUSTODY_ATOM]
        for i in range(0, len(bytez), BYTES_PER_CUSTODY_ATOM)
    ]
```

### `get_custody_secrets`

Extract the custody secrets from the signature

```python
def get_custody_secrets(key: BLSSignature) -> Sequence[int]:
    full_G2_element = bls.signature_to_G2(key)
    signature = full_G2_element[0].coeffs
    signature_bytes = b"".join(x.to_bytes(48, "little") for x in signature)
    secrets = [
        int.from_bytes(signature_bytes[i : i + BYTES_PER_CUSTODY_ATOM], "little")
        for i in range(0, len(signature_bytes), 32)
    ]
    return secrets
```

### `universal_hash_function`

```python
def universal_hash_function(
    data_chunks: Sequence[bytes], secrets: Sequence[int]
) -> int:
    n = len(data_chunks)
    return (
        sum(
            secrets[i % CUSTODY_SECRETS] ** i
            * int.from_bytes(atom, "little")
            % CUSTODY_PRIME
            for i, atom in enumerate(data_chunks)
        )
        + secrets[n % CUSTODY_SECRETS] ** n
    ) % CUSTODY_PRIME
```

### `compute_custody_bit`

```python
def compute_custody_bit(key: BLSSignature, data: ByteList) -> bit:
    custody_atoms = get_custody_atoms(data)
    secrets = get_custody_secrets(key)
    uhf = universal_hash_function(custody_atoms, secrets)
    legendre_bits = [
        legendre_bit(uhf + secrets[0] + i, CUSTODY_PRIME)
        for i in range(CUSTODY_PROBABILITY_EXPONENT)
    ]
    return bit(all(legendre_bits))
```

### `get_randao_epoch_for_custody_period`

```python
def get_randao_epoch_for_custody_period(
    period: uint64, validator_index: ValidatorIndex
) -> Epoch:
    next_period_start = (
        period + 1
    ) * EPOCHS_PER_CUSTODY_PERIOD - validator_index % EPOCHS_PER_CUSTODY_PERIOD
    return Epoch(next_period_start + CUSTODY_PERIOD_TO_RANDAO_PADDING)
```

### `get_custody_period_for_validator`

```python
def get_custody_period_for_validator(
    validator_index: ValidatorIndex, epoch: Epoch
) -> uint64:
    """
    Return the reveal period for a given validator.
    """
    return (
        epoch + validator_index % EPOCHS_PER_CUSTODY_PERIOD
    ) // EPOCHS_PER_CUSTODY_PERIOD
```

## Per-block processing

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_light_client_aggregate(state, block.body)
    process_operations(state, block.body)
    process_custody_game_operations(state, block.body)
```

### Custody Game Operations

```python
def process_custody_game_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    def for_ops(
        operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]
    ) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(body.chunk_challenges, process_chunk_challenge)
    for_ops(body.chunk_challenge_responses, process_chunk_challenge_response)
    for_ops(body.custody_key_reveals, process_custody_key_reveal)
    for_ops(body.early_derived_secret_reveals, process_early_derived_secret_reveal)
    for_ops(body.custody_slashings, process_custody_slashing)
```

#### Chunk challenges

```python
def process_chunk_challenge(
    state: BeaconState, challenge: CustodyChunkChallenge
) -> None:
    # Verify the attestation
    assert is_valid_indexed_attestation(
        state, get_indexed_attestation(state, challenge.attestation)
    )
    # Verify it is not too late to challenge the attestation
    max_attestation_challenge_epoch = Epoch(
        challenge.attestation.data.target.epoch + MAX_CHUNK_CHALLENGE_DELAY
    )
    assert get_current_epoch(state) <= max_attestation_challenge_epoch
    # Verify it is not too late to challenge the responder
    responder = state.validators[challenge.responder_index]
    if responder.exit_epoch < FAR_FUTURE_EPOCH:
        assert (
            get_current_epoch(state) <= responder.exit_epoch + MAX_CHUNK_CHALLENGE_DELAY
        )
    # Verify responder is slashable
    assert is_slashable_validator(responder, get_current_epoch(state))
    # Verify the responder participated in the attestation
    attesters = get_attesting_indices(state, challenge)
    assert challenge.responder_index in attesters
    # Verify shard transition is correctly given
    assert (
        hash_tree_root(challenge.shard_transition)
        == challenge.attestation.data.shard_transition_root
    )
    data_root = challenge.shard_transition.shard_data_roots[challenge.data_index]
    # Verify the challenge is not a duplicate
    for record in state.custody_chunk_challenge_records:
        assert (
            record.data_root != data_root or record.chunk_index != challenge.chunk_index
        )
    # Verify depth
    shard_block_length = challenge.shard_transition.shard_block_lengths[
        challenge.data_index
    ]
    transition_chunks = (
        shard_block_length + BYTES_PER_CUSTODY_CHUNK - 1
    ) // BYTES_PER_CUSTODY_CHUNK
    assert challenge.chunk_index < transition_chunks
    # Add new chunk challenge record
    new_record = CustodyChunkChallengeRecord(
        challenge_index=state.custody_chunk_challenge_index,
        challenger_index=get_beacon_proposer_index(state),
        responder_index=challenge.responder_index,
        inclusion_epoch=get_current_epoch(state),
        data_root=challenge.shard_transition.shard_data_roots[challenge.data_index],
        chunk_index=challenge.chunk_index,
    )
    replace_empty_or_append(state.custody_chunk_challenge_records, new_record)

    state.custody_chunk_challenge_index += 1
    # Postpone responder withdrawability
    responder.withdrawable_epoch = FAR_FUTURE_EPOCH
```

#### Custody chunk response

```python
def process_chunk_challenge_response(
    state: BeaconState, response: CustodyChunkResponse
) -> None:
    # Get matching challenge (if any) from records
    matching_challenges = [
        record
        for record in state.custody_chunk_challenge_records
        if record.challenge_index == response.challenge_index
    ]
    assert len(matching_challenges) == 1
    challenge = matching_challenges[0]
    # Verify chunk index
    assert response.chunk_index == challenge.chunk_index
    # Verify the chunk matches the crosslink data root
    assert is_valid_merkle_branch(
        leaf=hash_tree_root(response.chunk),
        branch=response.branch,
        depth=CUSTODY_RESPONSE_DEPTH + 1,  # Add 1 for the List length mix-in
        index=response.chunk_index,
        root=challenge.data_root,
    )
    # Clear the challenge
    index_in_records = state.custody_chunk_challenge_records.index(challenge)
    state.custody_chunk_challenge_records[index_in_records] = (
        CustodyChunkChallengeRecord()
    )
    # Reward the proposer
    proposer_index = get_beacon_proposer_index(state)
    increase_balance(
        state,
        proposer_index,
        Gwei(get_base_reward(state, proposer_index) // MINOR_REWARD_QUOTIENT),
    )
```

#### Custody key reveals

```python
def process_custody_key_reveal(state: BeaconState, reveal: CustodyKeyReveal) -> None:
    """
    Process ``CustodyKeyReveal`` operation.
    Note that this function mutates ``state``.
    """
    revealer = state.validators[reveal.revealer_index]
    epoch_to_sign = get_randao_epoch_for_custody_period(
        revealer.next_custody_secret_to_reveal, reveal.revealer_index
    )

    custody_reveal_period = get_custody_period_for_validator(
        reveal.revealer_index, get_current_epoch(state)
    )
    # Only past custody periods can be revealed, except after exiting the exit period can be revealed
    is_past_reveal = revealer.next_custody_secret_to_reveal < custody_reveal_period
    is_exited = revealer.exit_epoch <= get_current_epoch(state)
    is_exit_period_reveal = (
        revealer.next_custody_secret_to_reveal
        == get_custody_period_for_validator(
            reveal.revealer_index, revealer.exit_epoch - 1
        )
    )
    assert is_past_reveal or (is_exited and is_exit_period_reveal)

    # Revealed validator is active or exited, but not withdrawn
    assert is_slashable_validator(revealer, get_current_epoch(state))

    # Verify signature
    domain = get_domain(state, DOMAIN_RANDAO, epoch_to_sign)
    signing_root = compute_signing_root(epoch_to_sign, domain)
    assert bls.Verify(revealer.pubkey, signing_root, reveal.reveal)

    # Process reveal
    if is_exited and is_exit_period_reveal:
        revealer.all_custody_secrets_revealed_epoch = get_current_epoch(state)
    revealer.next_custody_secret_to_reveal += 1

    # Reward Block Proposer
    proposer_index = get_beacon_proposer_index(state)
    increase_balance(
        state,
        proposer_index,
        Gwei(get_base_reward(state, reveal.revealer_index) // MINOR_REWARD_QUOTIENT),
    )
```

#### Early derived secret reveals

```python
def process_early_derived_secret_reveal(
    state: BeaconState, reveal: EarlyDerivedSecretReveal
) -> None:
    """
    Process ``EarlyDerivedSecretReveal`` operation.
    Note that this function mutates ``state``.
    """
    revealed_validator = state.validators[reveal.revealed_index]
    derived_secret_location = uint64(
        reveal.epoch % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS
    )

    assert reveal.epoch >= get_current_epoch(state) + RANDAO_PENALTY_EPOCHS
    assert (
        reveal.epoch
        < get_current_epoch(state) + EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS
    )
    assert not revealed_validator.slashed
    assert (
        reveal.revealed_index
        not in state.exposed_derived_secrets[derived_secret_location]
    )

    # Verify signature correctness
    masker = state.validators[reveal.masker_index]
    pubkeys = [revealed_validator.pubkey, masker.pubkey]

    domain = get_domain(state, DOMAIN_RANDAO, reveal.epoch)
    signing_roots = [
        compute_signing_root(root, domain)
        for root in [hash_tree_root(reveal.epoch), reveal.mask]
    ]
    assert bls.AggregateVerify(pubkeys, signing_roots, reveal.reveal)

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
        increase_balance(
            state, whistleblower_index, whistleblowing_reward - proposer_reward
        )
        decrease_balance(state, reveal.revealed_index, penalty)

        # Mark this derived secret as exposed so validator cannot be punished repeatedly
        state.exposed_derived_secrets[derived_secret_location].append(
            reveal.revealed_index
        )
```

#### Custody Slashings

```python
def process_custody_slashing(
    state: BeaconState, signed_custody_slashing: SignedCustodySlashing
) -> None:
    custody_slashing = signed_custody_slashing.message
    attestation = custody_slashing.attestation

    # Any signed custody-slashing should result in at least one slashing.
    # If the custody bits are valid, then the claim itself is slashed.
    malefactor = state.validators[custody_slashing.malefactor_index]
    whistleblower = state.validators[custody_slashing.whistleblower_index]
    domain = get_domain(state, DOMAIN_CUSTODY_BIT_SLASHING, get_current_epoch(state))
    signing_root = compute_signing_root(custody_slashing, domain)
    assert bls.Verify(
        whistleblower.pubkey, signing_root, signed_custody_slashing.signature
    )
    # Verify that the whistleblower is slashable
    assert is_slashable_validator(whistleblower, get_current_epoch(state))
    # Verify that the claimed malefactor is slashable
    assert is_slashable_validator(malefactor, get_current_epoch(state))

    # Verify the attestation
    assert is_valid_indexed_attestation(
        state, get_indexed_attestation(state, attestation)
    )

    # TODO: can do a single combined merkle proof of data being attested.
    # Verify the shard transition is indeed attested by the attestation
    shard_transition = custody_slashing.shard_transition
    assert hash_tree_root(shard_transition) == attestation.data.shard_transition_root
    # Verify that the provided data matches the shard-transition
    assert (
        len(custody_slashing.data)
        == shard_transition.shard_block_lengths[custody_slashing.data_index]
    )
    assert (
        hash_tree_root(custody_slashing.data)
        == shard_transition.shard_data_roots[custody_slashing.data_index]
    )
    # Verify existence and participation of claimed malefactor
    attesters = get_attesting_indices(state, attestation)
    assert custody_slashing.malefactor_index in attesters

    # Verify the malefactor custody key
    epoch_to_sign = get_randao_epoch_for_custody_period(
        get_custody_period_for_validator(
            custody_slashing.malefactor_index, attestation.data.target.epoch
        ),
        custody_slashing.malefactor_index,
    )
    domain = get_domain(state, DOMAIN_RANDAO, epoch_to_sign)
    signing_root = compute_signing_root(epoch_to_sign, domain)
    assert bls.Verify(
        malefactor.pubkey, signing_root, custody_slashing.malefactor_secret
    )

    # Compute the custody bit
    computed_custody_bit = compute_custody_bit(
        custody_slashing.malefactor_secret, custody_slashing.data
    )

    # Verify the claim
    if computed_custody_bit == 1:
        # Slash the malefactor, reward the other committee members
        slash_validator(state, custody_slashing.malefactor_index)
        committee = get_beacon_committee(
            state, attestation.data.slot, attestation.data.index
        )
        others_count = len(committee) - 1
        whistleblower_reward = Gwei(
            malefactor.effective_balance
            // WHISTLEBLOWER_REWARD_QUOTIENT
            // others_count
        )
        for attester_index in attesters:
            if attester_index != custody_slashing.malefactor_index:
                increase_balance(state, attester_index, whistleblower_reward)
        # No special whistleblower reward: it is expected to be an attester. Others are free to slash too however.
    else:
        # The claim was false, the custody bit was correct. Slash the whistleblower that induced this work.
        slash_validator(state, custody_slashing.whistleblower_index)
```

## Per-epoch processing

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

    process_shard_epoch_increment(state)
```

### Handling of reveal deadlines

```python
def process_reveal_deadlines(state: BeaconState) -> None:
    epoch = get_current_epoch(state)
    for index, validator in enumerate(state.validators):
        deadline = validator.next_custody_secret_to_reveal + 1
        if get_custody_period_for_validator(ValidatorIndex(index), epoch) > deadline:
            slash_validator(state, ValidatorIndex(index))
```

```python
def process_challenge_deadlines(state: BeaconState) -> None:
    for custody_chunk_challenge in state.custody_chunk_challenge_records:
        if (
            get_current_epoch(state)
            > custody_chunk_challenge.inclusion_epoch + EPOCHS_PER_CUSTODY_PERIOD
        ):
            slash_validator(
                state,
                custody_chunk_challenge.responder_index,
                custody_chunk_challenge.challenger_index,
            )
            index_in_records = state.custody_chunk_challenge_records.index(
                custody_chunk_challenge
            )
            state.custody_chunk_challenge_records[index_in_records] = (
                CustodyChunkChallengeRecord()
            )
```

### Final updates

```python
def process_custody_final_updates(state: BeaconState) -> None:
    # Clean up exposed RANDAO key reveals
    state.exposed_derived_secrets[
        get_current_epoch(state) % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS
    ] = []

    # Reset withdrawable epochs if challenge records are empty
    records = state.custody_chunk_challenge_records
    validator_indices_in_records = set(
        record.responder_index for record in records
    )  # non-duplicate
    for index, validator in enumerate(state.validators):
        if validator.exit_epoch != FAR_FUTURE_EPOCH:
            not_all_secrets_are_revealed = (
                validator.all_custody_secrets_revealed_epoch == FAR_FUTURE_EPOCH
            )
            if (
                ValidatorIndex(index) in validator_indices_in_records
                or not_all_secrets_are_revealed
            ):
                # Delay withdrawable epochs if challenge records are not empty or not all
                # custody secrets revealed
                validator.withdrawable_epoch = FAR_FUTURE_EPOCH
            else:
                # Reset withdrawable epochs if challenge records are empty and all secrets are revealed
                if validator.withdrawable_epoch == FAR_FUTURE_EPOCH:
                    validator.withdrawable_epoch = Epoch(
                        validator.all_custody_secrets_revealed_epoch
                        + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
                    )
```
