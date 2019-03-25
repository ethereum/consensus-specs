# Ethereum 2.0 Phase 1 -- Custody Game

**NOTICE**: This spec is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

- [Ethereum 2.0 Phase 1 -- Custody Game](#ethereum-20-phase-1----custody-game)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Constants](#constants)
        - [Misc](#misc)
        - [Time parameters](#time-parameters)
        - [Max transactions per block](#max-transactions-per-block)
        - [Signature domains](#signature-domains)
    - [Data structures](#data-structures)
        - [Phase 0 updates](#phase-0-updates)
            - [`Validator`](#validator)
            - [`BeaconState`](#beaconstate)
            - [`BeaconBlockBody`](#beaconblockbody)
        - [Custody objects](#custody-objects)
            - [`DataChallenge`](#datachallenge)
            - [`DataChallengeRecord`](#datachallengerecord)
            - [`MixChallenge`](#mixchallenge)
            - [`MixChallengeRecord`](#mixchallengerecord)
            - [`CustodyResponse`](#custodyresponse)
            - [`CustodyReveal`](#custodyreveal)
    - [Helpers](#helpers)
        - [`get_attestation_chunk_count`](#get_attestation_chunk_count)
        - [`epoch_to_custody_period`](#epoch_to_custody_period)
        - [`verify_custody_reveal`](#verify_custody_reveal)
    - [Per-block processing](#per-block-processing)
        - [Transactions](#transactions)
            - [Custody reveals](#custody-reveals)
            - [Data challenges](#data-challenges)
            - [Mix challenges](#mix-challenges)
            - [Custody responses](#custody-responses)
    - [Per-epoch processing](#per-epoch-processing)

<!-- /TOC -->

## Introduction

This document details the beacon chain additions and changes in Phase 1 of Ethereum 2.0 to support the shard data custody game, building upon the [phase 0](0_beacon-chain.md) specification.

## Constants

### Misc

| Name | Value |
| - | - |
| `BYTES_PER_SHARD_BLOCK` | `2**14` (= 16,384) |
| `BYTES_PER_CHUNK` | `2**9` (= 512) |
| `MINOR_REWARD_QUOTIENT` | `2**8` (= 256) |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `MAX_DATA_CHALLENGE_DELAY` | `2**11` (= 2,048) | epochs | ~9 days |
| `EPOCHS_PER_CUSTODY_PERIOD` | `2**11` (= 2,048) | epochs | ~9 days |
| `CUSTODY_RESPONSE_DEADLINE` | `2**14` (= 16,384) | epochs | ~73 days |

### Max transactions per block

| Name | Value |
| - | - |
| `MAX_DATA_CHALLENGES` | `2**2` (= 4) |
| `MAX_MIX_CHALLENGES` | `2**1` (= 2) |
| `MAX_CUSTODY_RESPONSES` | `2**5` (= 32) |
| `MAX_CUSTODY_REVEALS` | `2**4` (= 16) |

### Signature domains

| Name | Value |
| - | - |
| `DOMAIN_CUSTODY_REVEAL` | `6` |
| `DOMAIN_MIX_CHALLENGE` | `7` |

## Data structures

### Phase 0 updates

Add the following fields to the end of the specified container objects. Fields of type `uint64` are initialized to `0` and list fields are initialized to `[]`.

#### `Validator`

```python
    'custody_reveals': 'uint64',
    'max_reveal_lateness': 'uint64',
```

#### `BeaconState`

```python
    'data_challenge_records': [DataChallengeRecord],
    'mix_challenge_records': [MixChallengeRecord],
    'challenge_index': 'uint64',
```

#### `BeaconBlockBody`

```python
    'custody_reveals': [CustodyReveal],
    'data_challenges': [DataChallenge],
    'mix_challenges': [MixChallenge],
    'custody_responses': [CustodyResponse],
```

### Custody objects

#### `DataChallenge`

```python
{
    'responder_index': ValidatorIndex,
    'chunk_index': 'uint64',
    'attestation': Attestation,
}
```

#### `DataChallengeRecord`

```python
{
    'challenge_index': 'uint64',
    'challenger_index': ValidatorIndex,
    'responder_index': ValidatorIndex,
    'deadline': 'uint64',
    'crosslink_data_root': 'bytes32',
    'depth': 'uint64',
    'chunk_index': 'uint64',
}
```

#### `MixChallenge`

```python
{
    'attestation': Attestation,
    'challenger_index': ValidatorIndex,
    'responder_index': ValidatorIndex,
    'responder_subkey': BLSSignature,
    'mix': 'bytes',
    'signature': BLSSignature,
}
```

#### `MixChallengeRecord`

```python
{
    'challenge_index': 'uint64',
    'challenger_index': ValidatorIndex,
    'responder_index': ValidatorIndex,
    'deadline': Epoch,
    'crosslink_data_root': Hash,
    'mix': 'bytes',
    'responder_subkey': BLSSignature,
}
```

#### `CustodyResponse`

```python
{
    'challenge_index': 'uint64',
    'data': ['byte', BYTES_PER_CHUNK],
    'branch': [Hash],
    'chunk_index': 'uint64',
}
```

#### `CustodyReveal`

```python
{
    'revealer_index': ValidatorIndex,
    'period': 'uint64',
    'subkey': BLSSignature,
    'masker_index': ValidatorIndex,
    'mask': 'bytes32',
}
```

## Helpers

### `get_attestation_chunk_count`

```python
def get_attestation_chunk_count(attestation: Attestation) -> int:
    attestation_start_epoch = attestation.data.latest_crosslink.epoch
    attestation_end_epoch = slot_to_epoch(attestation.data.slot)
    attestation_crosslink_length = min(MAX_CROSSLINK_EPOCHS, end_epoch - start_epoch)
    chunks_per_epoch = 2 * BYTES_PER_SHARD_BLOCK * SLOTS_PER_EPOCH // BYTES_PER_CHUNK
    return attestation_crosslink_length * chunks_per_epoch
```

### `epoch_to_custody_period`

```python
def epoch_to_custody_period(epoch: Epoch) -> int:
    return epoch // EPOCHS_PER_CUSTODY_PERIOD
```

### `verify_custody_reveal`

```python
def verify_custody_reveal(state: BeaconState,
                                 reveal: CustodyReveal) -> bool
    # Case 1: legitimate reveal
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
        signature=reveal.subkey,
        domain=get_domain(
            fork=state.fork,
            epoch=reveal.period * EPOCHS_PER_CUSTODY_PERIOD,
            domain_type=DOMAIN_CUSTODY_REVEAL,
        ),
    )
```

## Per-block processing

### Transactions

Add the following transactions to the per-block processing, in order the given below and after all other transactions in phase 0.

#### Custody reveals

Verify that `len(block.body.early_custody_reveals) <= MAX_CUSTODY_REVEALS`.

For each `reveal` in `block.body.early_custody_reveals`, run the following function:

```python
def process_custody_reveal(state: BeaconState,
                          reveal: CustodyReveal) -> None:
    assert verify_custody_reveal(reveal)
    revealer = state.validator_registry[reveal.revealer_index]

    # Case 1: Non-early non-punitive non-masked reveal
    if reveal.mask == ZERO_HASH:
        assert reveal.period == epoch_to_custody_period(revealer.activation_epoch) + revealer.custody_reveals
        # Revealer is active or exited
        assert is_active_validator(revealer, get_current_epoch(state)) or revealer.exit_epoch > get_current_epoch(state)
        revealer.custody_reveals += 1
        revealer.max_reveal_lateness = max(revealer.max_reveal_lateness, get_current_period(state) - reveal.period)

    # Case 2: Early punitive masked reveal
    else:
        assert reveal.period > epoch_to_custody_period(get_current_epoch(state))
        assert revealer.slashed is False
        slash_validator(state, reveal.revealer_index, reveal.masker_index)
        increase_balance(state, reveal.masker_index, base_reward(state, index) // MINOR_REWARD_QUOTIENT)

    proposer_index = get_beacon_proposer_index(state, state.slot)
    increase_balance(state, proposer_index, base_reward(state, index) // MINOR_REWARD_QUOTIENT)

```

#### Data challenges

Verify that `len(block.body.data_challenges) <= MAX_DATA_CHALLENGES`.

For each `challenge` in `block.body.data_challenges`, run the following function:

```python
def process_data_challenge(state: BeaconState,
                           challenge: DataChallenge) -> None:
    # Verify the attestation
    assert verify_standalone_attestation(state, convert_to_standalone(state, challenge.attestation))
    # Verify it is not too late to challenge
    assert slot_to_epoch(challenge.attestation.data.slot) >= get_current_epoch(state) - MAX_DATA_CHALLENGE_DELAY
    assert state.validator_registry[responder_index].exit_epoch >= get_current_epoch(state) - MAX_DATA_CHALLENGE_DELAY
    # Verify the responder participated in the attestation
    assert challenger.responder_index in challenge.attestation.validator_indices
    # Verify the challenge is not a duplicate
    for record in state.data_challenge_records:
        assert (
            record.crosslink_data_root != challenge.attestation.data.crosslink_crosslink_data_root or
            record.chunk_index != challenge.chunk_index
        )
    # Verify depth
    depth = math.log2(next_power_of_two(get_attestation_chunk_count(challenge.attestation)))
    assert challenge.chunk_index < 2**depth
    # Add new data challenge record
    state.data_challenge_records.append(DataChallengeRecord(
        challenge_index=state.challenge_index,
        challenger_index=get_beacon_proposer_index(state, state.slot),
        crosslink_data_root=challenge.attestation.data.crosslink_crosslink_data_root,
        depth=depth,
        deadline=get_current_epoch(state) + CUSTODY_RESPONSE_DEADLINE,
        chunk_index=challenge.chunk_index,
    ))
    state.challenge_index += 1
```

#### Mix challenges

Verify that `len(block.body.mix_challenges) <= MAX_MIX_CHALLENGES`.

For each `challenge` in `block.body.mix_challenges`, run the following function:

```python
def process_mix_challenge(state: BeaconState,
                          challenge: MixChallenge) -> None:
    # Verify challenge signature
    challenger = state.validator_registry[challenge.challenger_index]
    assert bls_verify(
        message_hash=signed_root(challenge),
        pubkey=challenger.pubkey,
        signature=challenge.signature,
        domain=get_domain(state, get_current_epoch(state), DOMAIN_MIX_CHALLENGE)
    )
    # Verify the challenger is not slashed
    assert challenger.slashed is False
    # Verify attestation
    assert verify_standalone_attestation(state, convert_to_standalone(state, challenge.attestation))
    # Verify the attestation is eligible for challenging
    responder = state.validator_registry[challenge.responder_index]
    min_challengeable_epoch = responder.exit_epoch - EPOCHS_PER_CUSTODY_PERIOD * (1 + responder.max_reveal_lateness)
    assert min_challengeable_epoch <= slot_to_epoch(challenge.attestation.data.slot) 
    # Verify the responder participated in the attestation
    assert challenge.responder_index in attestation.validator_indices
    # A validator can be the challenger or responder for at most one challenge at a time
    for challenge_record in state.mix_challenge_records:
        assert challenge_record.challenger_index != challenge.challenger_index
        assert challenge_record.responder_index != challenge.responder_index
    # Verify the responder subkey
    assert verify_custody_reveal(CustodyReveal(
        revealer_index=challenge.responder_index,
        period=epoch_to_custody_period(slot_to_epoch(attestation.data.slot)),
        subkey=challenge.responder_subkey,
    ))
    # Verify the mix's length and that its last bit is the opposite of the custody bit
    mix_length = get_attestation_chunk_count(challenge.attestation)
    verify_bitfield(challenge.mix, mix_length)
    custody_bit = get_bitfield_bit(attestation.custody_bitfield, attestation.validator_indices.index(responder_index))
    assert custody_bit != get_bitfield_bit(challenge.mix, mix_length - 1)
    # Add new mix challenge record
    state.mix_challenge_records.append(MixChallengeRecord(
        challenge_index=state.challenge_index,
        challenger_index=challenge.challenger_index,
        responder_index=challenge.responder_index,
        crosslink_data_root=challenge.attestation.crosslink_crosslink_data_root,
        mix=challenge.mix,
        responder_subkey=responder_subkey,
        deadline=get_current_epoch(state) + CUSTODY_RESPONSE_DEADLINE
    ))
    state.challenge_index += 1
    # Postpone responder withdrawability
    responder.withdrawable_epoch = FAR_FUTURE_EPOCH
```

#### Custody responses

Verify that `len(block.body.custody_responses) <= MAX_CUSTODY_RESPONSES`.

For each `response` in `block.body.custody_responses`, run the following function:

```python
def process_custody_response(state: BeaconState,
                            response: CustodyResponse) -> None:
    data_challenge = next(c for c in state.data_challenge_records if c.challenge_index == response.challenge_index, None)
    if data_challenge is not None:
        return process_data_challenge_response(state, response, data_challenge)

    mix_challenge = next(c for c in state.mix_challenge_records if c.challenge_index == response.challenge_index, None)
    if mix_challenge is not None:
        return process_mix_challenge_response(state, response, mix_challenge)

    assert False
```

```python
def process_data_challenge_response(state: BeaconState,
                                    response: CustodyResponse,
                                    challenge: DataChallengeRecord) -> None:
    assert verify_merkle_branch(
        leaf=hash_tree_root(response.data),
        branch=response.branch,
        depth=challenge.depth,
        index=challenge.chunk_index,
        root=challenge.crosslink_data_root,
    )
    # Check data index
    assert response.chunk_index == challenge.chunk_index
    # Must wait at least ENTRY_EXIT_DELAY before responding to a branch challenge
    assert get_current_epoch(state) >= challenge.inclusion_epoch + ENTRY_EXIT_DELAY
    state.data_challenge_records.remove(challenge)
    # Reward the proposer
    proposer_index = get_beacon_proposer_index(state, state.slot)
    increase_balance(state, proposer_index, base_reward(state, index) // MINOR_REWARD_QUOTIENT)
```

```python
def process_mix_challenge_response(state: BeaconState,
                                   response: CustodyResponse,
                                   challenge: MixChallengeRecord) -> None:
    # Check the data index is valid
    assert response.chunk_index < len(challenge.mix)
    # Check the provided data is part of the attested data
    assert verify_merkle_branch(
        leaf=hash_tree_root(response.data),
        branch=response.branch,
        depth=math.log2(next_power_of_two(len(challenge.mix))),
        index=response.chunk_index,
        root=challenge.crosslink_data_root,
    )
    # Check the mix bit (assert the response identified an invalid data index in the challenge)
    mix_bit = get_bitfield_bit(hash(challenge.responder_subkey + response.data), 0)
    previous_bit = 0 if response.chunk_index == 0 else get_bitfield_bit(challenge.mix, response.chunk_index - 1)
    next_bit = get_bitfield_bit(challenge.mix, response.chunk_index)
    assert previous_bit ^ mix_bit != next_bit
    # Resolve the challenge in favour of the responder
    slash_validator(state, challenge.challenger_index, challenge.responder_index)
    state.mix_challenge_records.remove(challenge)
```

## Per-epoch processing

Add the following loop immediately below the `process_ejections` loop:

```python
def process_challenge_deadlines(state: BeaconState) -> None:
    for challenge in state.data_challenge_records:
        if get_current_epoch(state) > challenge.deadline:
            slash_validator(state, challenge.responder_index, challenge.challenger_index)
            state.data_challenge_records.remove(challenge)

    for challenge in state.mix_challenge_records:
        if get_current_epoch(state) > challenge.deadline:
            slash_validator(state, challenge.responder_index, challenge.challenger_index)
            state.mix_challenge_records.remove(challenge)
        elif get_current_epoch(state) > state.validator_registry[challenge.responder_index].withdrawable_epoch:
            slash_validator(state, challenge.challenger_index, challenge.responder_index)
            state.mix_challenge_records.remove(challenge)
```

In `process_penalties_and_exits`, change the definition of `eligible` to the following (note that it is not a pure function because `state` is declared in the surrounding scope):

```python
def eligible(index):
    validator = state.validator_registry[index]
    # Cannot exit if there are still open data challenges
    if len([c for c in state.data_challenge_records if c.responder_index == index]) > 0:
        return False
    # Cannot exit if you have not revealed all of your subkeys
    elif epoch_to_custody_period(revealer.activation_epoch) + validator.custody_reveals <= epoch_to_custody_period(validator.exit_epoch):
        return False
    # Cannot exit if you already have
    elif validator.withdrawable_epoch < FAR_FUTURE_EPOCH:
        return False
    # Return minimum time
    else:
        return current_epoch >= validator.exit_epoch + MIN_VALIDATOR_WITHDRAWAL_EPOCHS
```
