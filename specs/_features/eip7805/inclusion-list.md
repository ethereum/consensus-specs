# EIP-7805 -- Inclusion List

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`InclusionListStore`](#inclusionliststore)
- [Helpers](#helpers)
  - [New `get_inclusion_list_store`](#new-get_inclusion_list_store)
  - [New `process_inclusion_list`](#new-process_inclusion_list)
  - [New `get_inclusion_list_transactions`](#new-get_inclusion_list_transactions)

<!-- mdformat-toc end -->

## Introduction

This is the inclusion list specification for the fork-choice enforced inclusion
list feature.

## Containers

### New containers

#### `InclusionListStore`

```python
@dataclass
class InclusionListStore(object):
    inclusion_lists: DefaultDict[Tuple[Slot, Root], Set[InclusionList]] = field(
        default_factory=lambda: defaultdict(set)
    )
    equivocators: DefaultDict[Tuple[Slot, Root], Set[ValidatorIndex]] = field(
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
    store: InclusionListStore, inclusion_list: InclusionList, is_before_view_freeze_deadline: bool
) -> None:
    key = (inclusion_list.slot, inclusion_list.inclusion_list_committee_root)

    # Ignore `inclusion_list` from equivocators.
    if inclusion_list.validator_index in store.equivocators[key]:
        return

    for stored_inclusion_list in store.inclusion_lists[key]:
        if stored_inclusion_list.validator_index != inclusion_list.validator_index:
            continue

        if stored_inclusion_list != inclusion_list:
            store.equivocators[key].add(inclusion_list.validator_index)
            store.inclusion_lists[key].remove(stored_inclusion_list)

        # Whether it was an equivocation or not, we have processed this `inclusion_list`.
        return

    # Only store `inclusion_list` if it arrived before the view freeze deadline.
    if is_before_view_freeze_deadline:
        store.inclusion_lists[key].add(inclusion_list)
```

### New `get_inclusion_list_transactions`

*Note*: `get_inclusion_list_transactions` returns a list of unique transactions
from all valid and non-equivocating `InclusionList`s that were received in a
timely manner on the p2p network for the given slot and for which the
`inclusion_list_committee_root` in the `InclusionList` matches the one
calculated based on the current state.

```python
def get_inclusion_list_transactions(
    store: InclusionListStore, state: BeaconState, slot: Slot
) -> Sequence[Transaction]:
    inclusion_list_committee = get_inclusion_list_committee(state, slot)
    inclusion_list_committee_root = hash_tree_root(inclusion_list_committee)
    key = (slot, inclusion_list_committee_root)

    inclusion_list_transactions = [
        transaction
        for inclusion_list in store.inclusion_lists[key]
        for transaction in inclusion_list.transactions
    ]

    # Deduplicate inclusion list transactions. Order does not need to be preserved.
    return list(set(inclusion_list_transactions))
```
