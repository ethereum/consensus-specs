# EIP-8369 -- Inclusion List

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Removed `get_inclusion_list_transactions`](#removed-get_inclusion_list_transactions)
  - [New `get_inclusion_list_transactions_by_member`](#new-get_inclusion_list_transactions_by_member)

<!-- mdformat-toc end -->

## Introduction

This document specifies the inclusion list helpers modified for EIP-8369.

## Helpers

### Removed `get_inclusion_list_transactions`

`get_inclusion_list_transactions` has been replaced by
`get_inclusion_list_transactions_by_member`, so that the execution engine
receives the inclusion lists grouped per committee member.

### New `get_inclusion_list_transactions_by_member`

*Note*: `get_inclusion_list_transactions_by_member` returns the transactions of
each valid and non-equivocating `InclusionList` for the given `slot` and
`dependent_root`, one list per inclusion list, ordered by validator index.
Transactions are not deduplicated and keep the order of their inclusion list, so
that the execution engine can meter work per inclusion list.

```python
def get_inclusion_list_transactions_by_member(
    store: InclusionListStore, slot: Slot, dependent_root: Root, only_timely: bool = True
) -> Sequence[Sequence[Transaction]]:
    key = (slot, dependent_root)
    inclusion_lists = store.inclusion_lists[key]
    equivocators = store.equivocators[key]

    transactions_by_member: list[Sequence[Transaction]] = []
    for validator_index in sorted(inclusion_lists.keys()):
        # Ignore inclusion lists from equivocators
        if validator_index in equivocators:
            continue

        # Ignore untimely inclusion lists if only timely ones are requested
        inclusion_list = inclusion_lists[validator_index]
        if only_timely and not inclusion_list.timely:
            continue

        transactions_by_member.append(inclusion_list.signed_inclusion_list.message.transactions)

    return transactions_by_member
```
