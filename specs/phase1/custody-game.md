# Ethereum 2.0 Phase 1 -- Custody Game

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
- [Constants](#constants)
  - [Misc](#misc)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters)
  - [Max operations per block](#max-operations-per-block)
  - [Reward and penalty quotients](#reward-and-penalty-quotients)
  - [Signature domain types](#signature-domain-types)
- [Data structures](#data-structures)
  - [New Beacon Chain operations](#new-beacon-chain-operations)
    - [`CustodySlashing`](#custodyslashing)
    - [`SignedCustodySlashing`](#signedcustodyslashing)
    - [`CustodyKeyReveal`](#custodykeyreveal)
    - [`EarlyDerivedSecretReveal`](#earlyderivedsecretreveal)
- [Helpers](#helpers)
  - [`legendre_bit`](#legendre_bit)
  - [`custody_atoms`](#custody_atoms)
  - [`compute_custody_bit`](#compute_custody_bit)
  - [`get_randao_epoch_for_custody_period`](#get_randao_epoch_for_custody_period)
  - [`get_custody_period_for_validator`](#get_custody_period_for_validator)
- [Per-block processing](#per-block-processing)
  - [Custody Game Operations](#custody-game-operations)
    - [Custody key reveals](#custody-key-reveals)
    - [Early derived secret reveals](#early-derived-secret-reveals)
    - [Custody Slashings](#custody-slashings)
- [Per-epoch processing](#per-epoch-processing)
  - [Handling of reveal deadlines](#handling-of-reveal-deadlines)
  - [Final updates](#final-updates)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document details the beacon chain additions and changes in Phase 1 of Ethereum 2.0 to support the shard data custody game, building upon the [Phase 0](../phase0/beacon-chain.md) specification.

## Constants

### Misc

| Name | Value | Unit |
| - | - |
| `BLS12_381_Q` | `4002409555221667393417789825735904156556882819939007885332058136124031650490837864442687629129015664037894272559787` |
| `BYTES_PER_CUSTODY_ATOM` | `48` | bytes |

## Configuration

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `RANDAO_PENALTY_EPOCHS` | `2**1` (= 2) | epochs | 12.8 minutes |
| `EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS` | `2**14` (= 16,384) | epochs | ~73 days |
| `EPOCHS_PER_CUSTODY_PERIOD` | `2**11` (= 2,048) | epochs | ~9 days |
| `CUSTODY_PERIOD_TO_RANDAO_PADDING` | `2**11` (= 2,048) | epochs | ~9 days |
| `MAX_REVEAL_LATENESS_DECREMENT` | `2**7` (= 128) | epochs | ~14 hours |

### Max operations per block

| Name | Value |
| - | - |
| `MAX_CUSTODY_KEY_REVEALS` | `2**8` (= 256) |
| `MAX_EARLY_DERIVED_SECRET_REVEALS` | `1` |
| `MAX_CUSTODY_SLASHINGS` | `1` |

### Reward and penalty quotients

| Name | Value |
| - | - |
| `EARLY_DERIVED_SECRET_REVEAL_SLOT_REWARD_MULTIPLE` | `2**1` (= 2) |
| `MINOR_REWARD_QUOTIENT` | `2**8` (= 256) |

### Signature domain types

The following types are defined, mapping into `DomainType` (little endian):

| Name | Value |
| - | - |
| `DOMAIN_CUSTODY_BIT_SLASHING` | `DomainType('0x83000000')` |

## Data structures

### New Beacon Chain operations

#### `CustodySlashing`

```python
class CustodySlashing(Container):
    # Attestation.custody_bits_blocks[data_index][committee.index(malefactor_index)] is the target custody bit to check.
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

### `custody_atoms`

Given one set of data, return the custody atoms: each atom will be combined with one legendre bit.

```python
def get_custody_atoms(bytez: bytes) -> Sequence[bytes]:
    bytez += b'\x00' * (-len(bytez) % BYTES_PER_CUSTODY_ATOM)  # right-padding
    return [bytez[i:i + BYTES_PER_CUSTODY_ATOM]
            for i in range(0, len(bytez), BYTES_PER_CUSTODY_ATOM)]
```

### `compute_custody_bit`

```python
def compute_custody_bit(key: BLSSignature, data: bytes) -> bit:
    full_G2_element = bls.signature_to_G2(key)
    s = full_G2_element[0].coeffs
    bits = [legendre_bit(sum(s[i % 2]**i * int.from_bytes(atom, "little")), BLS12_381_Q)
            for i, atom in enumerate(get_custody_atoms(data))]
    # XOR all atom bits
    return bit(sum(bits) % 2)
```

### `get_randao_epoch_for_custody_period`

```python
def get_randao_epoch_for_custody_period(period: uint64, validator_index: ValidatorIndex) -> Epoch:
    next_period_start = (period + 1) * EPOCHS_PER_CUSTODY_PERIOD - validator_index % EPOCHS_PER_CUSTODY_PERIOD
    return Epoch(next_period_start + CUSTODY_PERIOD_TO_RANDAO_PADDING)
```

### `get_custody_period_for_validator`

```python
def get_custody_period_for_validator(validator_index: ValidatorIndex, epoch: Epoch) -> int:
    '''
    Return the reveal period for a given validator.
    '''
    return (epoch + validator_index % EPOCHS_PER_CUSTODY_PERIOD) // EPOCHS_PER_CUSTODY_PERIOD
```


## Per-block processing

### Custody Game Operations

```python
def process_custody_game_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(body.custody_key_reveals, process_custody_key_reveal)
    for_ops(body.early_derived_secret_reveals, process_early_derived_secret_reveal)
    for_ops(body.custody_slashings, process_custody_slashing)
```

#### Custody key reveals

```python
def process_custody_key_reveal(state: BeaconState, reveal: CustodyKeyReveal) -> None:
    """
    Process ``CustodyKeyReveal`` operation.
    Note that this function mutates ``state``.
    """
    revealer = state.validators[reveal.revealer_index]
    epoch_to_sign = get_randao_epoch_for_custody_period(revealer.next_custody_secret_to_reveal, reveal.revealer_index)

    custody_reveal_period = get_custody_period_for_validator(reveal.revealer_index, get_current_epoch(state))
    assert revealer.next_custody_secret_to_reveal < custody_reveal_period

    # Revealed validator is active or exited, but not withdrawn
    assert is_slashable_validator(revealer, get_current_epoch(state))

    # Verify signature
    domain = get_domain(state, DOMAIN_RANDAO, epoch_to_sign)
    signing_root = compute_signing_root(epoch_to_sign, domain)
    assert bls.Verify(revealer.pubkey, signing_root, reveal.reveal)

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

    # Reward Block Proposer
    proposer_index = get_beacon_proposer_index(state)
    increase_balance(
        state,
        proposer_index,
        Gwei(get_base_reward(state, reveal.revealer_index) // MINOR_REWARD_QUOTIENT)
    )
```

#### Early derived secret reveals

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

    domain = get_domain(state, DOMAIN_RANDAO, reveal.epoch)
    signing_roots = [compute_signing_root(root, domain) for root in [hash_tree_root(reveal.epoch), reveal.mask]]
    assert bls.AggregateVerify(zip(pubkeys, signing_roots), reveal.reveal)

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

#### Custody Slashings

```python
def process_custody_slashing(state: BeaconState, signed_custody_slashing: SignedCustodySlashing) -> None:
    custody_slashing = signed_custody_slashing.message
    attestation = custody_slashing.attestation

    # Any signed custody-slashing should result in at least one slashing.
    # If the custody bits are valid, then the claim itself is slashed.
    malefactor = state.validators[custody_slashing.malefactor_index] 
    whistleblower = state.validators[custody_slashing.whistleblower_index]
    domain = get_domain(state, DOMAIN_CUSTODY_BIT_SLASHING, get_current_epoch(state))
    signing_root = compute_signing_root(custody_slashing, domain)
    assert bls.Verify(whistleblower.pubkey, signing_root, signed_custody_slashing.signature)
    # Verify that the whistleblower is slashable
    assert is_slashable_validator(whistleblower, get_current_epoch(state))
    # Verify that the claimed malefactor is slashable
    assert is_slashable_validator(malefactor, get_current_epoch(state))

    # Verify the attestation
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))

    # TODO: custody_slashing.data is not chunked like shard blocks yet, result is lots of padding.

    # TODO: can do a single combined merkle proof of data being attested.
    # Verify the shard transition is indeed attested by the attestation
    shard_transition = custody_slashing.shard_transition
    assert hash_tree_root(shard_transition) == attestation.shard_transition_root
    # Verify that the provided data matches the shard-transition
    assert hash_tree_root(custody_slashing.data) == shard_transition.shard_data_roots[custody_slashing.data_index]

    # Verify existence and participation of claimed malefactor
    attesters = get_attesting_indices(state, attestation.data, attestation.aggregation_bits)
    assert custody_slashing.malefactor_index in attesters
    
    # Verify the malefactor custody key
    epoch_to_sign = get_randao_epoch_for_custody_period(
        get_custody_period_for_validator(custody_slashing.malefactor_index, attestation.data.target.epoch),
        custody_slashing.malefactor_index,
    )
    domain = get_domain(state, DOMAIN_RANDAO, epoch_to_sign)
    signing_root = compute_signing_root(epoch_to_sign, domain)
    assert bls.Verify(malefactor.pubkey, signing_root, custody_slashing.malefactor_secret)

    # Get the custody bit
    custody_bits = attestation.custody_bits_blocks[custody_slashing.data_index]
    committee = get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    claimed_custody_bit = custody_bits[committee.index(custody_slashing.malefactor_index)]
    
    # Compute the custody bit
    computed_custody_bit = compute_custody_bit(custody_slashing.malefactor_secret, custody_slashing.data)
    
    # Verify the claim
    if claimed_custody_bit != computed_custody_bit:
        # Slash the malefactor, reward the other committee members
        slash_validator(state, custody_slashing.malefactor_index)
        others_count = len(committee) - 1
        whistleblower_reward = Gwei(malefactor.effective_balance // WHISTLEBLOWER_REWARD_QUOTIENT // others_count)
        for attester_index in attesters:
            if attester_index != custody_slashing.malefactor_index:
                increase_balance(state, attester_index, whistleblower_reward)
        # No special whisteblower reward: it is expected to be an attester. Others are free to slash too however. 
    else:
        # The claim was false, the custody bit was correct. Slash the whistleblower that induced this work.
        slash_validator(state, custody_slashing.whistleblower_index)
```


## Per-epoch processing

### Handling of reveal deadlines

Run `process_reveal_deadlines(state)` after `process_registry_updates(state)`:

```python
def process_reveal_deadlines(state: BeaconState) -> None:
    epoch = get_current_epoch(state)
    for index, validator in enumerate(state.validators):
        if get_custody_period_for_validator(ValidatorIndex(index), epoch) > validator.next_custody_secret_to_reveal:
            slash_validator(state, ValidatorIndex(index))
```

### Final updates

After `process_final_updates(state)`, additional updates are made for the custody game:

```python
def process_custody_final_updates(state: BeaconState) -> None:
    # Clean up exposed RANDAO key reveals
    state.exposed_derived_secrets[get_current_epoch(state) % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS] = []
```
