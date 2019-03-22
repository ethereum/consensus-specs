# Ethereum 2.0 Phase 1 -- Custody

**NOTICE**: This document is a work-in-progress for researchers and implementers. It reflects recent spec changes and takes precedence over the [Python proof-of-concept implementation](https://github.com/ethereum/beacon_chain).

## Table of contents

<!-- TOC -->

- [Ethereum 2.0 Phase 1 -- Custody](#ethereum-20-phase-1----custody)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Constants](#constants)
        - [Misc](#misc)
        - [Time parameters](#time-parameters)
        - [Max transactions per block](#max-transactions-per-block)
        - [Signature domains](#signature-domains)
    - [Data structures](#data-structures)
        - [Phase 0 object updates](#phase-0-object-updates)
            - [`Validator`](#validator)
            - [`BeaconBlockBody`](#beaconblockbody)
            - [`BeaconState`](#beaconstate)
        - [Custody objects](#custody-objects)
            - [`DataChallenge`](#datachallenge)
            - [`DataChallengeRecord`](#datachallengerecord)
            - [`CustodyChallenge`](#custodychallenge)
            - [`CustodyChallengeRecord`](#custodychallengerecord)
            - [`BranchResponse`](#branchresponse)
            - [`SubkeyReveal`](#subkeyreveal)
    - [Helpers](#helpers)
        - [`get_attestation_crosslink_length`](#get_attestation_crosslink_length)
        - [`get_mix_length_from_attestation`](#get_mix_length_from_attestation)
        - [`epoch_to_custody_period`](#epoch_to_custody_period)
        - [`slot_to_custody_period`](#slot_to_custody_period)
        - [`get_current_custody_period`](#get_current_custody_period)
        - [`verify_custody_subkey_reveal`](#verify_custody_subkey_reveal)
        - [`slash_validator`](#slash_validator)
    - [Per-block processing](#per-block-processing)
        - [Transactions](#transactions)
            - [Data challenges](#data-challenges)
            - [Subkey reveals](#subkey-reveals)
            - [Custody challenges](#custody-challenges)
            - [Branch responses](#branch-responses)
    - [Per-epoch processing](#per-epoch-processing)
    - [One-time phase 1 initiation transition](#one-time-phase-1-initiation-transition)

<!-- /TOC -->

## Introduction

This document details the beacon chain additions and changes in Phase 1 of Ethereum 2.0 to support custody, building upon the [phase 0](0_beacon-chain.md) specification.

## Constants

### Misc

| Name | Value |
| - | - |
| `BYTES_PER_SHARD_BLOCK` | `2**14` (= 16,384) |
| `BYTES_PER_MIX_CHUNK` | `2**9` (= 512) |
| `MINOR_REWARD_QUOTIENT` | `2**8` (= 256) |
| `EMPTY_PUBKEY` | `int_to_bytes48(0)` |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `MAX_DATA_CHALLENGE_DELAY` | 2**11 (= 2,048) | epochs | ~9 days |
| `CUSTODY_PERIOD_LENGTH` | 2**11 (= 2,048) | epochs | ~9 days |
| `PERSISTENT_COMMITTEE_PERIOD` | 2**11 (= 2,048) | epochs | ~9 days |
| `CHALLENGE_RESPONSE_DEADLINE` | 2**14 (= 16,384) | epochs | ~73 days |

### Max transactions per block

| Name | Value |
| - | - |
| `MAX_DATA_CHALLENGES` | `2**2` (= 4) |
| `MAX_CUSTODY_CHALLENGES` | `2**1` (= 2) |
| `MAX_BRANCH_RESPONSES` | `2**5` (= 32) |
| `MAX_EARLY_SUBKEY_REVEALS` | `2**4` (= 16) |

### Signature domains

| Name | Value |
| - | - |
| `DOMAIN_SHARD_PROPOSER` | `129` |
| `DOMAIN_SHARD_ATTESTER` | `130` |
| `DOMAIN_CUSTODY_SUBKEY` | `131` |
| `DOMAIN_CUSTODY_CHALLENGE` | `132` |

## Data structures

### Phase 0 object updates

Add the following fields to the end of the specified container objects.

#### `Validator`

```python
    'next_subkey_to_reveal': 'uint64',
    'max_reveal_lateness': 'uint64',
```

#### `BeaconBlockBody`

```python
    'data_challenges': [DataChallenge],
    'custody_challenges': [CustodyChallenge],
    'branch_responses': [BranchResponse],
    'subkey_reveals': [SubkeyReveal],
```

#### `BeaconState`

```python
    'data_challenge_records': [DataChallengeRecord],
    'custody_challenge_records': [CustodyChallengeRecord],
    'challenge_index': 'uint64',
```

### Custody objects

#### `DataChallenge`

```python
{
    'responder_index': 'uint64',
    'data_index': 'uint64',
    'attestation': SlashableAttestation,
}
```

#### `DataChallengeRecord`

```python
{
    'challenge_id': 'uint64',
    'challenger_index': 'uint64',
    'responder_index': 'uint64',
    'data_root': 'bytes32',
    'deadline': 'uint64',
    'depth': 'uint64',
    'data_index': 'uint64',
}
```

#### `CustodyChallenge`

```python
{
    'attestation': SlashableAttestation,
    'challenger_index': 'uint64',
    'responder_index': 'uint64',
    'responder_subkey': 'bytes96',
    'mix': 'bytes',
    'signature': 'bytes96',
}
```

#### `CustodyChallengeRecord`

```python
{
    'challenge_id': 'uint64',
    'challenger_index': 'uint64',
    'responder_index': 'uint64',
    'data_root': 'bytes32',
    'deadline': 'uint64',
    'challenge_mix': 'bytes',
    'responder_subkey': 'bytes96',
}
```

#### `BranchResponse`

```python
{
    'challenge_id': 'uint64',
    'data': ['byte', BYTES_PER_MIX_CHUNK],
    'branch': ['bytes32'],
    'data_index': 'uint64',
}
```

#### `SubkeyReveal`

```python
{
    'revealer_index': 'uint64',
    'period': 'uint64',
    'subkey': 'bytes96',
    'masker_index': 'uint64'
    'mask': 'bytes32',
}
```

## Helpers

### `get_attestation_crosslink_length`

```python
def get_attestation_crosslink_length(attestation: Attestation) -> int:
    start_epoch = attestation.data.latest_crosslink.epoch
    end_epoch = slot_to_epoch(attestation.data.slot)
    return min(MAX_CROSSLINK_EPOCHS, end_epoch - start_epoch)
```

### `get_mix_length_from_attestation`

```python
def get_mix_length_from_attestation(attestation: Attestation) -> int:
    chunks_per_slot = BYTES_PER_SHARD_BLOCK // BYTES_PER_MIX_CHUNK
    return get_attestation_crosslink_length(attestation) * EPOCH_LENGTH * chunks_per_slot
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
def verify_custody_subkey_reveal(state: BeaconState,
                                 reveal: SubkeyReveal) -> bool
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
            epoch=reveal.period * CUSTODY_PERIOD_LENGTH,
            domain_type=DOMAIN_CUSTODY_SUBKEY,
        ),
    )
```

### `slash_validator`

Change the definition of `slash_validator` as follows:

```python
def slash_validator(state: BeaconState, index: ValidatorIndex, whistleblower_index :ValidatorIndex=None) -> None:
    """
    Slash the validator of the given ``index``.
    Note that this function mutates ``state``.
    """
    exit_validator(state, index)
    validator = state.validator_registry[index]
    state.latest_slashed_balances[get_current_epoch(state) % LATEST_PENALIZED_EXIT_LENGTH] += get_effective_balance(state, index)
    
    proposer_index = get_beacon_proposer_index(state, state.slot)
    whistleblower_reward = get_effective_balance(state, index) // WHISTLEBLOWER_REWARD_QUOTIENT
    if whistleblower_index is None:
        increase_balance(state, proposer_index, whistleblower_reward)
    else:
        proposer_share = whistleblower_reward // INCLUDER_REWARD_QUOTIENT  # TODO: Define INCLUDER_REWARD_QUOTIENT
        increase_balance(state, proposer_index, proposer_share)
        increase_balance(state, whistleblower_index, whistleblower_reward - proposer_share)

    decrease_balance(state, index, whistleblower_reward)        
    validator.slashed_epoch = get_current_epoch(state)
    validator.withdrawable_epoch = get_current_epoch(state) + LATEST_PENALIZED_EXIT_LENGTH
```

The only change is that this introduces the possibility of a penalization where the "whistleblower" that takes credit is NOT the block proposer.

## Per-block processing

### Transactions

Add the following transactions to the per-block processing, in order the given below and after all other transactions in phase 0.

#### Data challenges

Verify that `len(block.body.data_challenges) <= MAX_DATA_CHALLENGES`.

For each `challenge` in `block.body.data_challenges`, run the following function:

```python
def process_data_challenge(state: BeaconState,
                           challenge: DataChallenge) -> None:
    # Check it is not too late to challenge
    assert slot_to_epoch(challenge.attestation.data.slot) >= get_current_epoch(state) - MAX_DATA_CHALLENGE_DELAY
    assert state.validator_registry[responder_index].exit_epoch >= get_current_epoch(state) - MAX_DATA_CHALLENGE_DELAY
    # Check the attestation is valid
    assert verify_slashable_attestation(state, challenge.attestation)
    # Check the responder participated
    assert challenger.responder_index in challenge.attestation.validator_indices
    # Check the challenge is not a duplicate
    for c in state.data_challenge_records:
        assert c.data_root != challenge.attestation.data.crosslink_data_root or c.data_index == challenge.data_index
    # Check validity of depth
    depth = log2(next_power_of_two(get_mix_length_from_attestation(challenge.attestation)))
    assert challenge.data_index < 2**depth
    # Add new data challenge record
    state.data_challenge_records.append(DataChallengeRecord(
        challenge_id=state.challenge_index,
        challenger_index=get_beacon_proposer_index(state, state.slot),
        data_root=challenge.attestation.data.compute_crosslink_data_root,
        depth=depth,
        deadline=get_current_epoch(state) + CHALLENGE_RESPONSE_DEADLINE,
        data_index=challenge.data_index,
    ))
    state.challenge_index += 1
```

#### Subkey reveals

Verify that `len(block.body.early_subkey_reveals) <= MAX_EARLY_SUBKEY_REVEALS`.

For each `reveal` in `block.body.early_subkey_reveals`, run the following function:

```python
def process_subkey_reveal(state: BeaconState,
                          reveal: SubkeyReveal) -> None:
    assert verify_custody_subkey_reveal(reveal)
    revealer = state.validator_registry[reveal.revealer_index]

    # Case 1: non-early non-punitive non-masked reveal
    if reveal.mask == ZERO_HASH:
        assert reveal.period == revealer.next_subkey_to_reveal
        # Revealer is active or exited
        assert is_active_validator(revealer) or revealer.exit_epoch > get_current_epoch(state)
        revealer.next_subkey_to_reveal += 1
        revealer.max_reveal_lateness = max(revealer.max_reveal_lateness, get_current_period(state) - reveal.period)

    # Case 2: Early punitive masked reveal
    else:
        assert reveal.period > get_current_custody_period(state)
        assert revealer.slashed is False
        slash_validator(state, reveal.revealer_index, reveal.masker_index)
        increase_balance(state, reveal.masker_index, base_reward(state, index) // MINOR_REWARD_QUOTIENT)

    proposer_index = get_beacon_proposer_index(state, state.slot)
    increase_balance(state, proposer_index, base_reward(state, index) // MINOR_REWARD_QUOTIENT)

```

#### Custody challenges

Verify that `len(block.body.custody_challenges) <= MAX_CUSTODY_CHALLENGES`.

For each `challenge` in `block.body.custody_challenges`, run the following function:

```python
def process_custody_challenge(state: BeaconState,
                      challenge: CustodyChallenge) -> None:
    challenger = state.validator_registry[challenge.challenger_index]
    responder = state.validator_registry[challenge.responder_index]
    # Verify the challenge signature
    assert bls_verify(
        message_hash=signed_root(challenge),
        pubkey=challenger.pubkey,
        signature=challenge.signature,
        domain=get_domain(state, get_current_epoch(state), DOMAIN_CUSTODY_CHALLENGE)
    )
    # Verify the challenged attestation
    assert verify_slashable_attestation(challenge.attestation, state)
    # Check the responder participated in the attestation
    assert challenge.responder_index in attestation.validator_indices
    # A validator can be the challenger or responder for at most one challenge at a time
    for challenge_record in state.custody_challenge_records:
        assert challenge_record.challenger_index != challenge.challenger_index
        assert challenge_record.responder_index != challenge.responder_index
    # Cannot challenge if slashed
    assert challenger.slashed is False
    # Verify the revealed subkey
    assert verify_custody_subkey_reveal(SubkeyReveal(
        revealer_index=challenge.responder_index,
        period=slot_to_custody_period(attestation.data.slot),
        subkey=challenge.responder_subkey,
    ))
    # Verify that the attestation is still eligible for challenging
    min_challengeable_epoch = responder.exit_epoch - CUSTODY_PERIOD_LENGTH * (1 + responder.max_reveal_lateness)
    assert min_challengeable_epoch <= slot_to_epoch(challenge.attestation.data.slot) 
    # Verify the mix's length and that its last bit is the opposite of the custody bit
    mix_length = get_mix_length_from_attestation(challenge.attestation)
    verify_bitfield(challenge.mix, mix_length)
    custody_bit = get_bitfield_bit(attestation.custody_bitfield, attestation.validator_indices.index(responder_index))
    assert custody_bit != get_bitfield_bit(challenge.mix, mix_length - 1)
    # Create a new challenge record
    state.custody_challenge_records.append(CustodyChallengeRecord(
        challenge_id=state.challenge_index,
        challenger_index=challenge.challenger_index,
        responder_index=challenge.responder_index,
        data_root=challenge.attestation.crosslink_data_root,
        challenge_mix=challenge.mix,
        responder_subkey=responder_subkey,
        deadline=get_current_epoch(state) + CHALLENGE_RESPONSE_DEADLINE
    ))
    state.challenge_index += 1
    # Postpone responder withdrawability
    state.validator_registry[responder_index].withdrawable_epoch = FAR_FUTURE_EPOCH
```

#### Branch responses

Verify that `len(block.body.branch_responses) <= MAX_BRANCH_RESPONSES`.

For each `response` in `block.body.branch_responses`, run the following function:

```python
def process_branch_response(state: BeaconState,
                            response: BranchResponse) -> None:
    data_challenge = next(c for c in state.data_challenge_records if c.challenge_id == response.challenge_id, None)
    if data_challenge is not None:
        return process_data_challenge_response(state, response, data_challenge)

    custody_challenge = next(c for c in state.custody_challenge_records if c.challenge_id == response.challenge_id, None)
    if custody_challenge is not None:
        return process_custody_challenge_response(state, response, custody_challenge)

    assert False
```

```python
def process_data_challenge_response(state: BeaconState,
                                    response: BranchResponse,
                                    challenge: DataChallengeRecord) -> None:
    assert verify_merkle_branch(
        leaf=hash_tree_root(response.data),
        branch=response.branch,
        depth=challenge.depth,
        index=challenge.data_index,
        root=challenge.data_root,
    )
    # Check data index
    assert response.data_index == challenge.data_index
    # Must wait at least ENTRY_EXIT_DELAY before responding to a branch challenge
    assert get_current_epoch(state) >= challenge.inclusion_epoch + ENTRY_EXIT_DELAY
    state.data_challenge_records.remove(challenge)
    # Reward the proposer
    proposer_index = get_beacon_proposer_index(state, state.slot)
    increase_balance(state, proposer_index, base_reward(state, index) // MINOR_REWARD_QUOTIENT)
```

A response to a custody challenge proves that a challenger's mix is invalid by pointing to an index where the mix is incorrect.

```python
def process_custody_challenge_response(state: BeaconState,
                                       response: BranchResponse,
                                       challenge: CustodyChallengeRecord) -> None:
    responder = state.validator_registry[challenge.responder_index]
    # Check the data index is valid
    assert response.data_index < len(challenge.mix)
    # Check the provided data is part of the attested data
    assert verify_merkle_branch(
        leaf=hash_tree_root(response.data),
        branch=response.branch,
        depth=log2(next_power_of_two(len(challenge.mix))),
        index=response.data_index,
        root=challenge.data_root,
    )
    # Check the mix bit (assert the response identified an invalid data index in the challenge)
    mix_bit = get_bitfield_bit(hash(challenge.responder_subkey + response.data), 0)
    previous_bit = 0 if response.data_index == 0 else get_bitfield_bit(challenge.mix, response.data_index - 1)
    next_bit = get_bitfield_bit(challenge.mix, response.data_index)
    assert previous_bit ^ mix_bit != next_bit
    # Resolve the challenge in the responder's favor
    slash_validator(state, challenge.challenger_index, challenge.responder_index)
    state.custody_challenge_records.remove(challenge)
```

## Per-epoch processing

Add the following loop immediately below the `process_ejections` loop:

```python
def process_challenge_deadlines(state: BeaconState) -> None:
    """
    Iterate through the challenges and slash validators that missed their deadline.
    """
    for challenge in state.data_challenge_records:
        if get_current_epoch(state) > challenge.deadline:
            slash_validator(state, challenge.responder_index, challenge.challenger_index)
            state.data_challenge_records.remove(challenge)

    for challenge in state.custody_challenge_records:
        if get_current_epoch(state) > challenge.deadline:
            slash_validator(state, challenge.responder_index, challenge.challenger_index)
            state.custody_challenge_records.remove(challenge)
        elif get_current_epoch(state) > state.validator_registry[challenge.responder_index].withdrawable_epoch:
            slash_validator(state, challenge.challenger_index, challenge.responder_index)
            state.custody_challenge_records.remove(challenge)
```

In `process_penalties_and_exits`, change the definition of `eligible` to the following (note that it is not a pure function because `state` is declared in the surrounding scope):

```python
def eligible(index):
    validator = state.validator_registry[index]
    # Cannot exit if there are still open data challenges
    if len([c for c in state.data_challenge_records if c.responder_index == index]) > 0:
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
    'max_reveal_lateness': 0,
```

Update the `BeaconState` to the new format and fill the new member values with:

```python
    'data_challenge_records': [],
    'custody_challenge_records': [],
    'challenge_index': 0,
```
