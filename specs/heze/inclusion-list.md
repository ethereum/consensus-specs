# Heze -- Inclusion List

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`InclusionListEntry`](#inclusionlistentry)
    - [`InclusionListStore`](#inclusionliststore)
- [Helpers](#helpers)
  - [New `get_inclusion_list_store`](#new-get_inclusion_list_store)
  - [New `process_inclusion_list`](#new-process_inclusion_list)
  - [New `get_inclusion_list_transactions`](#new-get_inclusion_list_transactions)
  - [New `get_inclusion_list_bits`](#new-get_inclusion_list_bits)
  - [New `is_inclusion_list_bits_inclusive`](#new-is_inclusion_list_bits_inclusive)

<!-- mdformat-toc end -->

## Introduction

These are the inclusion list specifications to implement Heze.

## Containers

### New containers

#### `InclusionListEntry`

```python
@dataclass(eq=True, frozen=True)
class InclusionListEntry:
    signed_inclusion_list: SignedInclusionList
    timely: Boolean
```

#### `InclusionListStore`

```python
@dataclass
class InclusionListStore:
    inclusion_lists: DefaultDict[Tuple[Slot, Root], Dict[ValidatorIndex, InclusionListEntry]]
    equivocators: DefaultDict[Tuple[Slot, Root], Set[ValidatorIndex]]
```

## Helpers

### New `get_inclusion_list_store`

```python
def get_inclusion_list_store() -> InclusionListStore:
    # `cached_or_new_inclusion_list_store` is implementation and context dependent.
    # It returns the cached `InclusionListStore`; if none exists,
    # it initializes a new instance, caches it and returns it.
    inclusion_list_store = cached_or_new_inclusion_list_store()

    return inclusion_list_store
```

### New `process_inclusion_list`

```python
def process_inclusion_list(
    store: InclusionListStore, signed_inclusion_list: SignedInclusionList, timely: bool
) -> None:
    inclusion_list = signed_inclusion_list.message
    validator_index = inclusion_list.validator_index

    inclusion_lists = store.inclusion_lists[(inclusion_list.slot, inclusion_list.dependent_root)]
    equivocators = store.equivocators[(inclusion_list.slot, inclusion_list.dependent_root)]

    if validator_index in inclusion_lists:
        # Mark the validator as an equivocator if it published a different inclusion list
        stored_inclusion_list = inclusion_lists[validator_index].signed_inclusion_list.message
        if stored_inclusion_list != inclusion_list:
            equivocators.add(validator_index)

        # Ignore an inclusion list that has already been processed
        return

    # Store the signed inclusion list and its timeliness
    inclusion_lists[validator_index] = InclusionListEntry(
        signed_inclusion_list=signed_inclusion_list,
        timely=timely,
    )
```

### New `get_inclusion_list_transactions`

*Note*: `get_inclusion_list_transactions` returns a list of unique transactions
from all valid and non-equivocating `InclusionList`s for the given `slot` and
`dependent_root`. When `only_timely` is `True`, only `InclusionList`s received
in a timely manner on the p2p network are considered; otherwise, timeliness is
not considered.

*Note*: Inclusion lists MUST be retained for at least
`MIN_SLOTS_FOR_INCLUSION_LISTS_REQUESTS` slots beyond their slot, after which
they MAY be pruned.

```python
def get_inclusion_list_transactions(
    store: InclusionListStore, slot: Slot, dependent_root: Root, only_timely: bool = True
) -> Sequence[Transaction]:
    inclusion_lists = store.inclusion_lists[(slot, dependent_root)]
    equivocators = store.equivocators[(slot, dependent_root)]

    transactions: list[Transaction] = []
    for validator_index, inclusion_list in inclusion_lists.items():
        # Ignore inclusion lists from equivocators
        if validator_index in equivocators:
            continue

        # Ignore untimely inclusion lists if only timely ones are requested
        if only_timely and not inclusion_list.timely:
            continue

        transactions.extend(inclusion_list.signed_inclusion_list.message.transactions)

    # Deduplicate inclusion list transactions. Order does not need to be preserved.
    return list(set(transactions))
```

### New `get_inclusion_list_bits`

```python
def get_inclusion_list_bits(
    store: InclusionListStore,
    state: BeaconState,
    slot: Slot,
    dependent_root: Root,
    only_timely: bool = True,
) -> InclusionListBits:
    inclusion_lists = store.inclusion_lists[(slot, dependent_root)]
    equivocators = store.equivocators[(slot, dependent_root)]

    validator_indices = []
    for validator_index, inclusion_list in inclusion_lists.items():
        # Ignore inclusion lists from equivocators
        if validator_index in equivocators:
            continue

        # Ignore untimely inclusion lists if only timely ones are requested
        if only_timely and not inclusion_list.timely:
            continue

        validator_indices.append(validator_index)

    committee = get_inclusion_list_committee(state, slot)
    return InclusionListBits(validator_index in validator_indices for validator_index in committee)
```

### New `is_inclusion_list_bits_inclusive`

```python
def is_inclusion_list_bits_inclusive(
    store: InclusionListStore,
    state: BeaconState,
    slot: Slot,
    dependent_root: Root,
    inclusion_list_bits: InclusionListBits,
    only_timely: bool = True,
) -> bool:
    local_inclusion_list_bits = get_inclusion_list_bits(
        store, state, slot, dependent_root, only_timely
    )

    for i in range(INCLUSION_LIST_COMMITTEE_SIZE):
        if local_inclusion_list_bits[i] and not inclusion_list_bits[i]:
            return False
    return True
```
