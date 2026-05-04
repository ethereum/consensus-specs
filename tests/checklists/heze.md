# Heze Test Checklist

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=2 --minlevel=2 -->

- [`test_inclusion_list_store_transaction_uniqueness`](#test_inclusion_list_store_transaction_uniqueness)
- [`test_inclusion_list_store_by_slot_and_committee_root`](#test_inclusion_list_store_by_slot_and_committee_root)
- [`test_inclusion_list_store_equivocation`](#test_inclusion_list_store_equivocation)
- [`test_inclusion_list_store_equivocation_scope`](#test_inclusion_list_store_equivocation_scope)
- [`test_inclusion_list_store_view_freeze_cutoff`](#test_inclusion_list_store_view_freeze_cutoff)

<!-- mdformat-toc end -->

## `test_inclusion_list_store_transaction_uniqueness`

### Status

Implemented ✅

### Description

Stored IL transactions should be unique.

### Scenario

Process empty, non-empty and full-sized ILs. Some ILs have overlapping
transactions.

### Expectation

All ILs should be processed successfully and all transactions in the IL store
should be unique.

## `test_inclusion_list_store_by_slot_and_committee_root`

### Status

Implemented ✅

### Description

ILs are stored by slot and IL committee root.

### Scenario

Process ILs with the same slot but different IL committee roots.

### Expectation

Fetching ILs by slot and IL committee root should return ILs with the given slot
and IL committee root.

## `test_inclusion_list_store_equivocation`

### Status

Implemented ✅

### Description

ILs from equivocators should not be stored.

### Scenario

Process ILs, two of which are equivocations.

### Expectation

The first IL from an equivocator should be stored successfully, which should be
removed from the IL store after processing the second IL from the equivocator.
Subsequent ILs from the equivocator should be ignored. Any non-equivocating ILs
should not be affected.

## `test_inclusion_list_store_equivocation_scope`

### Status

Implemented ✅

### Description

Equivocation consequences are slot-bound: equivocators are allowed to
participate in subsequent slots.

### Scenario

Equivocate and then participate in the next slot.

### Expectation

All ILs from the equivocator in that slot should be ignored. However, a
non-equivocating IL from the equivocator in the next slot should be stored.

## `test_inclusion_list_store_view_freeze_cutoff`

### Status

Implemented ✅

### Description

ILs received after the view freeze cutoff should be ignored unless it's an
equivocation.

### Scenario

Process ILs before and after the view freeze cutoff while equivocating after the
cutoff.

### Expectation

An IL received after the view freeze cutoff should not be stored. An
equivocation detected after the cutoff should be handled.
