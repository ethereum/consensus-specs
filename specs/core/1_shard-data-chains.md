# Ethereum 2.0 Phase 1 -- Shard Data Chains

**NOTICE**: This document is a work-in-progress for researchers and implementers. It reflects recent spec changes and takes precedence over the [Python proof-of-concept implementation](https://github.com/ethereum/beacon_chain).

At the current stage, Phase 1, while fundamentally feature-complete, is still subject to change. Development teams with spare resources may consider starting on the "Shard chains and crosslink data" section; at least basic properties, such as the fact that a shard block can get created every slot and is dependent on both a parent block in the same shard and a beacon chain block at or before that same slot, are unlikely to change, though details are likely to undergo similar kinds of changes to what Phase 0 has undergone since the start of the year.

## Table of contents

<!-- TOC -->

- [Ethereum 2.0 Phase 1 -- Shard Data Chains](#ethereum-20-phase-1----shard-data-chains)
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
        - [Shard blocks](#shard-blocks)
            - [`ShardBlock`](#shardblock)
            - [`ShardBlockHeader`](#shardblockheader)
            - [`ShardAttestation`](#shardattestation)
        - [Custody objects](#custody-objects)
            - [`DataChallenge`](#datachallenge)
            - [`DataChallengeRecord`](#datachallengerecord)
            - [`CustodyChallenge`](#custodychallenge)
            - [`CustodyChallengeRecord`](#custodychallengerecord)
            - [`BranchResponse`](#branchresponse)
            - [`SubkeyReveal`](#subkeyreveal)
    - [Shard chains and crosslink data](#shard-chains-and-crosslink-data)
        - [Helper functions](#helper-functions)
            - [`get_split_offset`](#get_split_offset)
            - [`get_shuffled_committee`](#get_shuffled_committee)
            - [`get_persistent_committee`](#get_persistent_committee)
            - [`get_shard_proposer_index`](#get_shard_proposer_index)
        - [Shard fork choice rule](#shard-fork-choice-rule)
        - [Shard attestation processing](#shard-attestation-processing)
    - [Updates to the beacon chain](#updates-to-the-beacon-chain)
        - [Helpers](#helpers)
            - [`get_data_challenge_record`](#get_data_challenge_record)
            - [`get_custody_challenge_record`](#get_custody_challenge_record)
            - [`get_attestation_crosslink_length`](#get_attestation_crosslink_length)
            - [`get_attestation_mix_chunk_count`](#get_attestation_mix_chunk_count)
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

This document represents the specification for Phase 1 of Ethereum 2.0 -- Shard Data Chains, building upon the [phase 0](0_beacon-chain.md) specification.

Ethereum 2.0 consists of a central beacon chain along with `SHARD_COUNT` shards. Phase 1 is primarily concerned with the construction, validity, and consensus on the _data_ of these shard chains. Phase 1 does not specify shard chain state execution or account balances. This is left for future phases.

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
    'reveal_max_periods_late': 'uint64',
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

### Shard blocks

#### `ShardBlock`

```python
{
    'slot': 'uint64',
    'shard': 'uint64',
    'previous_block_root': 'bytes32',
    'beacon_chain_reference': 'bytes32',
    'data': ['byte', BYTES_PER_SHARD_BLOCK],
    'state_root': 'bytes32',
    'signature': 'bytes96',
}
```

#### `ShardBlockHeader`

```python
{
    'slot': 'uint64',
    'shard': 'uint64',
    'previous_block_root': 'bytes32',
    'beacon_chain_reference': 'bytes32',
    'data_root': 'bytes32',
    'state_root': 'bytes32',
    'signature': 'bytes96',
}
```

#### `ShardAttestation`

```python
{
    'header': ShardBlockHeader,
    'participation_bitfield': 'bytes',
    'aggregate_signature': 'bytes96',
}
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
    'data': ['byte', BYTES_PER_CHUNK],
    'branch': ['bytes32'],
    'data_index': 'uint64',
}
```

#### `SubkeyReveal`

```python
{
    'validator_index': 'uint64',
    'period': 'uint64',
    'subkey': 'bytes96',
    'mask': 'bytes32',
    'revealer_index': 'uint64'
}
```

## Shard chains and crosslink data

### Helper functions

#### `get_split_offset`

````python
def get_split_offset(list_size: int, chunks: int, index: int) -> int:
    """
    Returns a value such that for a list L, chunk count k and index i,
    split(L, k)[i] == L[get_split_offset(len(L), k, i): get_split_offset(len(L), k, i + 1)]
    """
    return (list_size * index) // chunks
````

#### `get_shuffled_committee`

```python
def get_shuffled_committee(state: BeaconState,
                           shard: Shard,
                           committee_start_epoch: Epoch,
                           index: int,
                           committee_count: int) -> List[ValidatorIndex]:
    """
    Return shuffled committee.
    """
    active_validator_indices = get_active_validator_indices(state.validator_registry, committee_start_epoch)
    length = len(active_validator_indices)
    start_offset = get_split_offset(length, SHARD_COUNT * committee_count, shard * committee_count + index)
    end_offset = get_split_offset(length, SHARD_COUNT * committee_count, shard * committee_count + index + 1)
    return [
        active_validator_indices[get_permuted_index(index, length, generate_seed(state, committee_start_epoch))]
        for i in range(start_offset, end_offset)
    ]
```

#### `get_persistent_committee`

```python
def get_persistent_committee(state: BeaconState,
                             shard: Shard,
                             slot: Slot) -> List[ValidatorIndex]:
    """
    Return the persistent committee for the given ``shard`` at the given ``slot``.
    """
    earlier_start_epoch = epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD * 2
    later_start_epoch = epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD

    committee_count = max(
        len(get_active_validator_indices(state.validator_registry, earlier_start_epoch)) //
        (SHARD_COUNT * TARGET_COMMITTEE_SIZE),
        len(get_active_validator_indices(state.validator_registry, later_start_epoch)) //
        (SHARD_COUNT * TARGET_COMMITTEE_SIZE),
    ) + 1
    
    index = slot % committee_count
    earlier_committee = get_shuffled_committee(state, shard, earlier_start_epoch, index, committee_count)
    later_committee = get_shuffled_committee(state, shard, later_start_epoch, index, committee_count)

    def get_switchover_epoch(index):
        return bytes_to_int(hash(earlier_seed + bytes3(index))[0:8]) % PERSISTENT_COMMITTEE_PERIOD

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
    # Randomly shift persistent committee
    persistent_committee = get_persistent_committee(state, shard, slot)
    seed = hash(state.current_shuffling_seed + int_to_bytes8(shard) + int_to_bytes8(slot))
    random_index = bytes_to_int(seed[0:8]) % len(persistent_committee)
    persistent_committee = persistent_committee[random_index:] + persistent_committee[:random_index]

    # Try to find an active proposer
    for index in persistent_committee:
        if is_active_validator(state.validator_registry[index], get_current_epoch(state)):
            return index

    # No block can be proposed if no validator is active
    return None
```

### Shard fork choice rule

For a `ShardBlockHeader` object `header` to be processed by a node the following conditions must be met:

* The `header.previous_block_root` is the hash a of `ShardBlock` that has been processed and accepted.
* The `header.beacon_chain_reference` is the hash of a `BeaconBlock` in the canonical beacon chain with slot less than or equal to `header.slot`.
* The `header.beacon_chain_reference` is equal to or a descendant of the `beacon_chain_reference` specified in the `ShardBlock` pointed to by `header.previous_block_root`.
* The `ShardBlock` object `shard_block` with the same root as `header` has been downloaded.

The fork choice rule for any shard is LMD GHOST using the shard chain attestations of the persistent committee and the beacon chain attestations of the crosslink committee currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (i.e. `state.crosslinks[shard].shard_block_root`). Only blocks whose `beacon_chain_reference` is the block in the main beacon chain at the specified `slot` should be considered. (If the beacon chain skips a slot, then the block at that slot is considered to be the block in the beacon chain at the highest slot lower than a slot.)

### Shard attestation processing

Given a `shard_attestation` let `state` be the `BeaconState` referred to by `shard_attestation.header.beacon_chain_reference` and run `verify_shard_attestation(state, shard_attestation)`.

```python
def verify_shard_attestation(state: BeaconState, shard_attestation: ShardAttestation) -> None:
    header = shard_attestation.header

    # Check proposer signature
    proposer_index = get_shard_proposer_index(state, header.shard, header.slot)
    assert proposer_index is not None
    assert bls_verify(
        pubkey=validators[proposer_index].pubkey,
        message_hash=signed_root(header),
        signature=header.signature,
        domain=get_domain(state, slot_to_epoch(header.slot), DOMAIN_SHARD_PROPOSER)
    )

    # Check attestations
    persistent_committee = get_persistent_committee(state, header.shard, header.slot)
    assert verify_bitfield(shard_attestation.participation_bitfield, len(persistent_committee))
    for i in range(len(persistent_committee)):
        if not is_active_validator(state.validator_registry[persistent_committee[i]], get_current_epoch(state)):
            assert get_bitfield_bit(shard_attestation.participation_bitfield, i) == 0b0
    aggregate_pubkey = bls_aggregate_pubkeys([
        state.validator_registry[index].pubkey for i, index in enumerate(persistent_committee)
        if get_bitfield_bit(shard_attestation.participation_bitfield, i) == 0b1
    ])
    assert bls_verify(
        pubkey=aggregate_pubkey,
        message_hash=header.previous_block_root,
        signature=shard_attestation.aggregate_signature,
        domain=get_domain(state, slot_to_epoch(header.slot), DOMAIN_SHARD_ATTESTER)
    )
```

## Updates to the beacon chain

### Helpers

#### `get_data_challenge_record`

```python
def get_data_challenge_record(state: BeaconState, id: int) -> DataChallengeRecord:
    records = [c for c in state.data_challenges if c.challenge_id == id]
    return records[0] if len(records) > 0 else None
```

#### `get_custody_challenge_record`

```python
def get_custody_challenge_record(state: BeaconState, id: int) -> CustodyChallengeRecord:
    records = [c for c in state.custody_challenges if c.challenge_id == id]
    return records[0] if len(records) > 0 else None
```

#### `get_attestation_crosslink_length`

```python
def get_attestation_crosslink_length(attestation: Attestation) -> int:
    start_epoch = attestation.data.latest_crosslink.epoch
    end_epoch = slot_to_epoch(attestation.data.slot)
    return min(MAX_CROSSLINK_EPOCHS, end_epoch - start_epoch)
```

#### `get_attestation_mix_chunk_count`

```python
def get_attestation_mix_chunk_count(attestation: Attestation) -> int:
    chunks_per_slot = BYTES_PER_SHARD_BLOCK // BYTES_PER_MIX_CHUNK
    return get_attestation_crosslink_length(attestation) * EPOCH_LENGTH * chunks_per_slot
```

#### `epoch_to_custody_period`

```python
def epoch_to_custody_period(epoch: Epoch) -> int:
    return epoch // CUSTODY_PERIOD_LENGTH
```

#### `slot_to_custody_period`

```python
def slot_to_custody_period(slot: Slot) -> int:
    return epoch_to_custody_period(slot_to_epoch(slot))
```

#### `get_current_custody_period`

```python
def get_current_custody_period(state: BeaconState) -> int:
    return epoch_to_custody_period(get_current_epoch(state))
```

#### `verify_custody_subkey_reveal`

```python
def verify_custody_subkey_reveal(state: BeaconState,
                                 reveal: SubkeyReveal) -> bool
    # Case 1: legitimate reveal
    if reveal.mask == ZERO_HASH:
        pubkeys=[state.validator_registry[reveal.validator_index].pubkey]
        message_hashes=[hash_tree_root(reveal.period)]

    # Case 2: punitive early reveal
    # Masking prevents proposer stealing the whistleblower reward
    # Secure under the aggregate extraction infeasibility assumption
    # See pages 11-12 of https://crypto.stanford.edu/~dabo/pubs/papers/aggreg.pdf
    else:
        pubkeys.append(state.validator_registry[reveal.revealer_index].pubkey)
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

#### `slash_validator`

Change the definition of `slash_validator` as follows:

```python
def slash_validator(state: BeaconState, index: ValidatorIndex, whistleblower_index=None:ValidatorIndex) -> None:
    """
    Slash the validator of the given ``index``.
    Note that this function mutates ``state``.
    """
    exit_validator(state, index)
    validator = state.validator_registry[index]
    state.latest_slashed_balances[get_current_epoch(state) % LATEST_PENALIZED_EXIT_LENGTH] += get_effective_balance(state, index)
    
    block_proposer_index = get_beacon_proposer_index(state, state.slot)
    whistleblower_reward = get_effective_balance(state, index) // WHISTLEBLOWER_REWARD_QUOTIENT
    if whistleblower_index is None:
        state.validator_balances[block_proposer_index] += whistleblower_reward
    else:
        state.validator_balances[whistleblower_index] += (
            whistleblower_reward * INCLUDER_REWARD_QUOTIENT // (INCLUDER_REWARD_QUOTIENT + 1)
        )
        state.validator_balances[block_proposer_index] += whistleblower_reward // (INCLUDER_REWARD_QUOTIENT + 1)
    state.validator_balances[index] -= whistleblower_reward
    validator.slashed_epoch = get_current_epoch(state)
    validator.withdrawable_epoch = get_current_epoch(state) + LATEST_PENALIZED_EXIT_LENGTH
```

The only change is that this introduces the possibility of a penalization where the "whistleblower" that takes credit is NOT the block proposer.

### Per-block processing

#### Transactions

Add the following transactions to the per-block processing, in order the given below and after all other transactions in phase 0.

##### Data challenges

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
    depth = log2(next_power_of_two(get_attestation_mix_chunk_count(challenge.attestation)))
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

##### Subkey reveals

Verify that `len(block.body.early_subkey_reveals) <= MAX_EARLY_SUBKEY_REVEALS`.

For each `reveal` in `block.body.early_subkey_reveals`, run the following function:

```python
def process_subkey_reveal(state: BeaconState,
                          reveal: SubkeyReveal) -> None:
    assert verify_custody_subkey_reveal(reveal)

    # Either the reveal is of a future period, or it is of the current period and the validator is still active
    is_early_reveal = reveal.period > get_current_custody_period(state) or (
        reveal.period == get_current_custody_period(state) and
        state.validator_registry[reveal.validator_index].exit_epoch > get_current_epoch(state)
    )

    if is_early_reveal:
        assert state.validator_registry[reveal.validator_index].slashed_epoch > get_current_epoch(state)
        slash_validator(state, reveal.validator_index, reveal.revealer_index)
        state.validator_balances[reveal.revealer_index] += base_reward(state, index) // MINOR_REWARD_QUOTIENT
    elif reveal.period == state.validator_registry[reveal.validator_index].next_subkey_to_reveal and reveal.mask == ZERO_HASH:
        # Revealing a past subkey, or a current subkey for a validator that has exited
        proposer_index = get_beacon_proposer_index(state, state.slot)
        state.validator_balances[proposer_index] += base_reward(state, index) // MINOR_REWARD_QUOTIENT
        state.validator_registry[reveal.validator_index].next_subkey_to_reveal += 1
        state.validator_registry[reveal.validator_index].reveal_max_periods_late = max(
            state.validator_registry[reveal.validator_index].reveal_max_periods_late,
            get_current_period(state) - reveal.period
        )
    else:
        assert False
```

##### Custody challenges

Verify that `len(block.body.custody_challenges) <= MAX_CUSTODY_CHALLENGES`.

For each `challenge` in `block.body.custody_challenges`, run the following function:

```python
def process_challenge(state: BeaconState,
                      challenge: CustodyChallenge) -> None:
    challenger = state.validator_registry[challenge.challenger_index]
    responder = state.validator_registry[challenge.responder_index]
    # Verify the signature
    assert bls_verify(
        message_hash=signed_root(challenge),
        pubkey=challenger.pubkey,
        signature=challenge.signature,
        domain=get_domain(state, get_current_epoch(state), DOMAIN_CUSTODY_CHALLENGE)
    )
    # Verify the attestation
    assert verify_slashable_attestation(challenge.attestation, state)
    # Check the responder participated in the attestation
    assert challenge.responder_index in attestation.validator_indices
    # Any validator can be a challenger or responder of max 1 challenge at a time
    for c in state.custody_challenge_records:
        assert c.challenger_index != challenge.challenger_index
        assert c.responder_index != challenge.responder_index
    # Cannot challenge if you have been slashed
    assert challenger.slashed is False
    # Make sure the revealed subkey is valid
    assert verify_custody_subkey_reveal(SubkeyReveal(
        validator_index=responder_index,
        period=slot_to_custody_period(attestation.data.slot),
        subkey=challenge.responder_subkey,
    ))
    # Verify that the attestation is still eligible for challenging
    min_challengeable_epoch = responder.exit_epoch - CUSTODY_PERIOD_LENGTH * (1 + responder.reveal_max_periods_late)
    assert min_challengeable_epoch <= slot_to_epoch(challenge.attestation.data.slot) 
    # Verify the mix's length and that its last bit is the opposite of the attested bit
    mix_length = get_attestation_mix_chunk_count(challenge.attestation)
    verify_bitfield(challenge.mix, mix_length)
    attested_bit = get_bitfield_bit(attestation.custodyfield, attestation.validator_indices.index(responder_index))
    assert attested_bit != get_bitfield_bit(challenge.mix, mix_length - 1)
    # Create a new challenge object
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
    # Responder cannot withdraw yet!
    state.validator_registry[responder_index].withdrawable_epoch = FAR_FUTURE_EPOCH
```

##### Branch responses

Verify that `len(block.body.branch_responses) <= MAX_BRANCH_RESPONSES`.

For each `response` in `block.body.branch_responses`, run the following function:

```python
def process_branch_response(state: BeaconState,
                            response: BranchResponse) -> None:
    data_challenge = get_data_challenge_record(response.challenge_id)
    if data_challenge is not None:
        return process_data_challenge_response(state, response, data_challenge)

    custody_challenge = get_custody_challenge_record(response.challenge_id)
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
    state.validator_balances[proposer_index] += base_reward(state, index) // MINOR_REWARD_QUOTIENT
```

A response to a custody challenge proves that a challenger's mix is invalid by pointing to an index where the mix is incorrect.

```python
def process_custody_challenge_response(state: BeaconState,
                                       response: BranchResponse,
                                       challenge: CustodyChallengeRecord) -> None:
    challenge = get_custody_challenge_record(state, response.challenge_id)
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

### Per-epoch processing

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
    if [c for c in state.data_challenge_records if c.responder_index == index] != []:
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

### One-time phase 1 initiation transition

Run the following on the fork block after per-slot processing and before per-block and per-epoch processing.

For all `validator` in `ValidatorRegistry`, update it to the new format and fill the new member values with:

```python
    'next_subkey_to_reveal': get_current_custody_period(state),
    'reveal_max_periods_late': 0,
```

Update the `BeaconState` to the new format and fill the new member values with:

```python
    'data_challenge_records': [],
    'custody_challenge_records': [],
    'challenge_index': 0,
```
