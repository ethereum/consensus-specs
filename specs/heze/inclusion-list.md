# Heze -- Inclusion List

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Containers](#containers)
  - [New containers](#new-containers)
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

#### `InclusionListStore`

```python
@dataclass
class InclusionListStore:
    inclusion_lists: DefaultDict[Root, Dict[Root, SignedInclusionList]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    inclusion_list_timeliness: Dict[Root, Boolean] = field(default_factory=dict)
    equivocators: DefaultDict[Root, Set[ValidatorIndex]] = field(
        default_factory=lambda: defaultdict(set)
    )
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
    store: InclusionListStore,
    signed_inclusion_list: SignedInclusionList,
    inclusion_list_committee_root: Root,
    is_timely: bool,
) -> None:
    inclusion_list = signed_inclusion_list.message
    key = inclusion_list_committee_root

    # Ignore an inclusion list that has already been stored
    inclusion_list_root = hash_tree_root(inclusion_list)
    if inclusion_list_root in store.inclusion_lists[key]:
        return

    # Ignore inclusion lists from equivocators
    if inclusion_list.validator_index in store.equivocators[key]:
        return

    # Mark the validator as an equivocator if it published a different inclusion list
    for stored_signed_inclusion_list in store.inclusion_lists[key].values():
        if stored_signed_inclusion_list.message.validator_index == inclusion_list.validator_index:
            store.equivocators[key].add(inclusion_list.validator_index)
            return

    # Store the signed inclusion list and its timeliness
    store.inclusion_lists[key][inclusion_list_root] = signed_inclusion_list
    store.inclusion_list_timeliness[inclusion_list_root] = is_timely
```

### New `get_inclusion_list_transactions`

*Note*: `get_inclusion_list_transactions` returns a list of unique transactions
from all valid and non-equivocating `InclusionList`s for the given slot and for
which the `inclusion_list_committee_root` compatible with the `dependent_root`
in the `InclusionList` matches the one calculated from the given `state`. When
`only_timely` is `True`, only `InclusionList`s received in a timely manner on
the p2p network are considered; otherwise, timeliness is not considered.

*Note*: Inclusion lists MUST be retained for at least
`MIN_SLOTS_FOR_INCLUSION_LISTS_REQUESTS` slots beyond their slot, after which
they MAY be pruned.

```python
def get_inclusion_list_transactions(
    store: InclusionListStore, state: BeaconState, slot: Slot, only_timely: bool = True
) -> Sequence[Transaction]:
    committee = get_inclusion_list_committee(state, slot)
    key = hash_tree_root(committee)

    inclusion_lists = store.inclusion_lists[key]
    equivocators = store.equivocators[key]
    timeliness = store.inclusion_list_timeliness

    transactions: list[Transaction] = []
    for inclusion_list_root in inclusion_lists:
        inclusion_list = inclusion_lists[inclusion_list_root].message

        # Ignore inclusion lists from equivocators
        if inclusion_list.validator_index in equivocators:
            continue

        # Ignore untimely inclusion lists if only timely ones are requested
        if only_timely and not timeliness[inclusion_list_root]:
            continue

        transactions.extend(inclusion_list.transactions)

    # Deduplicate inclusion list transactions. Order does not need to be preserved.
    return list(set(transactions))
```

### New `get_inclusion_list_bits`

```python
def get_inclusion_list_bits(
    store: InclusionListStore, state: BeaconState, slot: Slot, only_timely: bool = True
) -> InclusionListBits:
    """
    Return a ``BitVector`` over inclusion list committee indices with bits set
    for those who provided valid, non-equivocating inclusion lists for the given ``slot``.
    """
    committee = get_inclusion_list_committee(state, slot)
    key = hash_tree_root(committee)

    inclusion_lists = store.inclusion_lists[key]
    equivocators = store.equivocators[key]
    timeliness = store.inclusion_list_timeliness

    validator_indices = []
    for inclusion_list_root in inclusion_lists:
        inclusion_list = inclusion_lists[inclusion_list_root].message

        # Ignore inclusion lists from equivocators
        if inclusion_list.validator_index in equivocators:
            continue

        # Ignore untimely inclusion lists if only timely ones are requested
        if only_timely and not timeliness[inclusion_list_root]:
            continue

        validator_indices.append(inclusion_list.validator_index)

    return InclusionListBits(
        data=[validator_index in validator_indices for validator_index in committee]
    )
```

### New `is_inclusion_list_bits_inclusive`

```python
def is_inclusion_list_bits_inclusive(
    store: InclusionListStore,
    state: BeaconState,
    slot: Slot,
    inclusion_list_bits: InclusionListBits,
    only_timely: bool = True,
) -> bool:
    """
    Return ``True`` if and only if ``inclusion_list_bits`` has a bit set for
    every bit set in the local inclusion list bits for the given ``slot``.
    """
    local_inclusion_list_bits = get_inclusion_list_bits(store, state, slot, only_timely)

    for i in range(INCLUSION_LIST_COMMITTEE_SIZE):
        if local_inclusion_list_bits[i] and not inclusion_list_bits[i]:
            return False
    return True
```
