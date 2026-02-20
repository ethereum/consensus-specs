# Heze -- Honest Builder

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Builder activities](#builder-activities)
  - [Constructing the `SignedExecutionPayloadBid`](#constructing-the-signedexecutionpayloadbid)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
builder" to implement Heze.

## Builder activities

### Constructing the `SignedExecutionPayloadBid`

*Note*: The only change made to `SignedExecutionPayloadBid` is to set
`bid.inclusion_list_bits` based on the builder's local view of inclusion lists.

1. Set `bid.inclusion_list_bits` to
   `get_inclusion_list_bits(get_inclusion_list_store(), state, Slot(bid.slot - 1))`.
