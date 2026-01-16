# EIP-7805 -- The Beacon Chain

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Domain types](#domain-types)
- [Preset](#preset)
  - [Inclusion list committee](#inclusion-list-committee)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`InclusionList`](#inclusionlist)
    - [`SignedInclusionList`](#signedinclusionlist)
- [Helpers](#helpers)
  - [Predicates](#predicates)
    - [New `is_valid_inclusion_list_signature`](#new-is_valid_inclusion_list_signature)
  - [Beacon state accessors](#beacon-state-accessors)
    - [New `get_inclusion_list_committee`](#new-get_inclusion_list_committee)

<!-- mdformat-toc end -->

## Introduction

These are the beacon-chain specifications to add EIP-7805 / fork-choice
enforced, committee-based inclusion list (FOCIL) mechanism to allow forced
transaction inclusion. Refers to the following posts:

- [Fork-Choice enforced Inclusion Lists (FOCIL): A simple committee-based inclusion list proposal](https://ethresear.ch/t/fork-choice-enforced-inclusion-lists-focil-a-simple-committee-based-inclusion-list-proposal/19870/1)
- [FOCIL CL & EL workflow](https://ethresear.ch/t/focil-cl-el-workflow/20526)

*Note*: This specification is built upon [Fulu](../../fulu/beacon-chain.md).

## Constants

### Domain types

| Name                              | Value                      |
| --------------------------------- | -------------------------- |
| `DOMAIN_INCLUSION_LIST_COMMITTEE` | `DomainType('0x0C000000')` |

## Preset

### Inclusion list committee

| Name                            | Value                |
| ------------------------------- | -------------------- |
| `INCLUSION_LIST_COMMITTEE_SIZE` | `uint64(2**4)` (=16) |

## Containers

### New containers

#### `InclusionList`

```python
class InclusionList(Container):
    slot: Slot
    validator_index: ValidatorIndex
    inclusion_list_committee_root: Root
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
```

#### `SignedInclusionList`

```python
class SignedInclusionList(Container):
    message: InclusionList
    signature: BLSSignature
```

## Helpers

### Predicates

#### New `is_valid_inclusion_list_signature`

```python
def is_valid_inclusion_list_signature(
    state: BeaconState, signed_inclusion_list: SignedInclusionList
) -> bool:
    """
    Check if ``signed_inclusion_list`` has a valid signature.
    """
    message = signed_inclusion_list.message
    index = message.validator_index
    pubkey = state.validators[index].pubkey
    domain = get_domain(state, DOMAIN_INCLUSION_LIST_COMMITTEE, compute_epoch_at_slot(message.slot))
    signing_root = compute_signing_root(message, domain)
    return bls.Verify(pubkey, signing_root, signed_inclusion_list.signature)
```

### Beacon state accessors

#### New `get_inclusion_list_committee`

```python
def get_inclusion_list_committee(
    state: BeaconState, slot: Slot
) -> Vector[ValidatorIndex, INCLUSION_LIST_COMMITTEE_SIZE]:
    epoch = compute_epoch_at_slot(slot)
    seed = get_seed(state, epoch, DOMAIN_INCLUSION_LIST_COMMITTEE)
    indices = get_active_validator_indices(state, epoch)
    start = (slot % SLOTS_PER_EPOCH) * INCLUSION_LIST_COMMITTEE_SIZE
    end = start + INCLUSION_LIST_COMMITTEE_SIZE
    return Vector[ValidatorIndex, INCLUSION_LIST_COMMITTEE_SIZE](
        [
            indices[compute_shuffled_index(uint64(i % len(indices)), uint64(len(indices)), seed)]
            for i in range(start, end)
        ]
    )
```
