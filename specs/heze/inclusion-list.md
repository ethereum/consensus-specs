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
  - [New `get_inclusion_lists`](#new-get_inclusion_lists)
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
    timely: bool
```

#### `InclusionListStore`

```python
@dataclass
class InclusionListStore:
    inclusion_list_entries: defaultdict[tuple[Slot, Root], dict[ValidatorIndex, InclusionListEntry]]
    equivocators: defaultdict[tuple[Slot, Root], set[ValidatorIndex]]
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
    key = (inclusion_list.slot, inclusion_list.dependent_root)

    if validator_index in store.inclusion_list_entries[key]:
        # Mark the validator as an equivocator if it published a different inclusion list
        stored_entry = store.inclusion_list_entries[key][validator_index]
        stored_inclusion_list = stored_entry.signed_inclusion_list.message
        if stored_inclusion_list != inclusion_list:
            store.equivocators[key].add(validator_index)

        # Ignore an inclusion list that has already been processed
        return

    # Store the signed inclusion list and its timeliness
    store.inclusion_list_entries[key][validator_index] = InclusionListEntry(
        signed_inclusion_list=signed_inclusion_list,
        timely=timely,
    )
```

### New `get_inclusion_lists`

*Note*: `get_inclusion_lists` returns a list of valid and non-equivocating
`InclusionList`s for the given `slot` and `dependent_root` in committee order.
When `only_timely` is `True`, only `InclusionList`s received in a timely manner
on the p2p network are considered; otherwise, timeliness is not considered.
Missing `InclusionList`s are represented by empty elements, as are untimely
`InclusionList`s when `only_timely` is `True`.

*Note*: Inclusion lists MUST be retained for at least
`MIN_SLOTS_FOR_INCLUSION_LISTS_REQUESTS` slots beyond their slot, after which
they MAY be pruned.

```python
def get_inclusion_lists(
    store: InclusionListStore,
    committee: InclusionListCommittee,
    slot: Slot,
    dependent_root: Root,
    only_timely: bool = True,
) -> Sequence[Sequence[Transaction]]:
    key = (slot, dependent_root)
    inclusion_list_entries = store.inclusion_list_entries.get(key, {})
    equivocators = store.equivocators.get(key, set())

    inclusion_lists: list[Sequence[Transaction]] = []
    for validator_index in committee:
        entry = inclusion_list_entries.get(validator_index)
        if entry is None:
            inclusion_lists.append([])
            continue
        if validator_index in equivocators:
            inclusion_lists.append([])
            continue
        if only_timely and not entry.timely:
            inclusion_lists.append([])
            continue

        inclusion_lists.append(list(entry.signed_inclusion_list.message.transactions))

    return inclusion_lists
```

### New `get_inclusion_list_bits`

```python
def get_inclusion_list_bits(
    store: InclusionListStore,
    committee: InclusionListCommittee,
    slot: Slot,
    dependent_root: Root,
    only_timely: bool = True,
) -> InclusionListBits:
    key = (slot, dependent_root)
    inclusion_list_entries = store.inclusion_list_entries.get(key, {})
    equivocators = store.equivocators.get(key, set())

    validator_indices = []
    for validator_index, inclusion_list in inclusion_list_entries.items():
        if validator_index in equivocators:
            continue
        if only_timely and not inclusion_list.timely:
            continue

        validator_indices.append(validator_index)

    return InclusionListBits(data=[index in validator_indices for index in committee])
```

### New `is_inclusion_list_bits_inclusive`

```python
def is_inclusion_list_bits_inclusive(
    store: InclusionListStore,
    committee: InclusionListCommittee,
    slot: Slot,
    dependent_root: Root,
    inclusion_list_bits: InclusionListBits,
    only_timely: bool = True,
) -> bool:
    local_inclusion_list_bits = get_inclusion_list_bits(
        store, committee, slot, dependent_root, only_timely
    )

    for i in range(INCLUSION_LIST_COMMITTEE_SIZE):
        if local_inclusion_list_bits[i] and not inclusion_list_bits[i]:
            return False
    return True
```
