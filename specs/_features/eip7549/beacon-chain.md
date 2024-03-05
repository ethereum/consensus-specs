# EIP-7549 -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Preset](#preset)
- [Containers](#containers)
  - [Modified containers](#modified-containers)
    - [Attestation](#attestation)
    - [IndexedAttestation](#indexedattestation)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [`get_committee_indices`](#get_committee_indices)
  - [Beacon state accessors](#beacon-state-accessors)
    - [New `get_committee_attesters`](#new-get_committee_attesters)
    - [Modified `get_attesting_indices`](#modified-get_attesting_indices)
  - [Block processing](#block-processing)
    - [Modified `process_attestation`](#modified-process_attestation)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to move the attestation committee index outside of the signed message. For motivation, refer to [EIP-7549](https://eips.ethereum.org/EIPS/eip-7549).

*Note:* This specification is built upon [Deneb](../../deneb/beacon_chain.md) and is under active development.

## Preset

| Name | Value | Description |
| - | - | - |
| `MAX_ATTESTER_SLASHINGS` | `2**0` (= 1) |
| `MAX_ATTESTATIONS`       | `2**3` (= 8) |

## Containers

### Modified containers

#### Attestation

```python
class Attestation(Container):
     aggregation_bits: List[Bitlist[MAX_VALIDATORS_PER_COMMITTEE], MAX_COMMITTEES_PER_SLOT]  # [Modified in EIP7549]
     data: AttestationData
     committee_bits: Bitvector[MAX_COMMITTEES_PER_SLOT]  # [New in EIP7549]
     signature: BLSSignature
```

#### IndexedAttestation

```python
class IndexedAttestation(Container):
    attesting_indices: List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT]  # [Modified in EIP7549]
    data: AttestationData
    signature: BLSSignature
```

## Helper functions

### Misc

#### `get_committee_indices`

```python
def get_committee_indices(commitee_bits: Bitvector) -> List[CommitteeIndex]:
     return [CommitteeIndex(index) for bit, index in enumerate(commitee_bits) if bit]
```

### Beacon state accessors

#### New `get_committee_attesters`

```python
def get_committee_attesters(state: BeaconState, attesting_bits: Bitlist, index: CommitteeIndex) -> Set[ValidatorIndex]:
    committee = get_beacon_committee(state, data.slot, index)
    return set(index for i, index in enumerate(committee) if attesting_bits[i])
```

#### Modified `get_attesting_indices`

```python
def get_attesting_indices(state: BeaconState, attestation: Attestation) -> Set[ValidatorIndex]:
    """
    Return the set of attesting indices corresponding to ``aggregation_bits`` and ``committee_bits``.
    """

    output = set()
    committee_indices = get_committee_indices(attestation.committee_bits)
    for index in committee_indices:
        attesting_bits = attestation.attesting_bits[index]
        committee_attesters = get_committee_attesters(state, attesting_bits, index)
        output = output.union(committee_attesters)

    return output
```

### Block processing

#### Modified `process_attestation`

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.target.epoch == compute_epoch_at_slot(data.slot)
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot

    # [Modified in EIP7549]
    assert data.index == 0
    committee_indices = get_committee_indices(attestation.committee_bits)
    assert len(committee_indices) > 0
    assert len(committee_indices) == len(attestation.aggregation_bits)
    for index in committee_indices:
        assert index < get_committee_count_per_slot(state, data.target.epoch)
        committee = get_beacon_committee(state, data.slot, index)
        assert len(attestation.aggregation_bits[index]) == len(committee)

    # Participation flag indices
    participation_flag_indices = get_attestation_participation_flag_indices(state, data, state.slot - data.slot)

    # Verify signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))

    # Update epoch participation flags
    if data.target.epoch == get_current_epoch(state):
        epoch_participation = state.current_epoch_participation
    else:
        epoch_participation = state.previous_epoch_participation

    proposer_reward_numerator = 0
    for index in get_attesting_indices(state, attestation):
        for flag_index, weight in enumerate(PARTICIPATION_FLAG_WEIGHTS):
            if flag_index in participation_flag_indices and not has_flag(epoch_participation[index], flag_index):
                epoch_participation[index] = add_flag(epoch_participation[index], flag_index)
                proposer_reward_numerator += get_base_reward(state, index) * weight

    # Reward proposer
    proposer_reward_denominator = (WEIGHT_DENOMINATOR - PROPOSER_WEIGHT) * WEIGHT_DENOMINATOR // PROPOSER_WEIGHT
    proposer_reward = Gwei(proposer_reward_numerator // proposer_reward_denominator)
    increase_balance(state, get_beacon_proposer_index(state), proposer_reward)
```
