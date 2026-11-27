# Heze -- Honest Builder

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Builder activities](#builder-activities)
  - [Constructing the `SignedExecutionPayloadBid`](#constructing-the-signedexecutionpayloadbid)
  - [Constructing the `SignedExecutionPayloadEnvelope`](#constructing-the-signedexecutionpayloadenvelope)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
builder" to implement Heze.

## Builder activities

### Constructing the `SignedExecutionPayloadBid`

Builders should set `bid.inclusion_list_bits` based on their inclusion list
view, which comprises all valid and non-equivocating inclusion lists they have
observed, and set `bid.inclusion_list_exemptions_root` to the `hash_tree_root`
of the inclusion list exemptions returned by `get_payload`.

1. Set `bid.inclusion_list_bits` to
   `get_inclusion_list_bits(get_inclusion_list_store(), inclusion_list_committee, slot, dependent_root, only_timely=False)`,
   where `inclusion_list_committee` is
   `get_inclusion_list_committee(state, slot)`, `dependent_root` is
   `get_shuffling_dependent_root(store, bid.parent_block_root, compute_epoch_at_slot(slot))`,
   `slot` is `bid.slot - 1`, and `store` is the fork choice store.
2. Set `inclusion_list_exemptions_root` to
   `hash_tree_root(inclusion_list_exemptions)`, where
   `inclusion_list_exemptions` is the `InclusionListExemptions` field returned
   by `engine_getPayloadV7`.

### Constructing the `SignedExecutionPayloadEnvelope`

1. Set `envelope.inclusion_list_exemptions` to be the `InclusionListExemptions`
   associated with `payload`.
