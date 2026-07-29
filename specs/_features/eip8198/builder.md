# EIP-8198 -- Honest Builder

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Builder activities](#builder-activities)
  - [Constructing the `SignedExecutionPayloadBid`](#constructing-the-signedexecutionpayloadbid)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
builder" to implement EIP-8198.

*Note*: This specification is built upon [Heze](../../heze/builder.md).

## Builder activities

### Constructing the `SignedExecutionPayloadBid`

*Note*: The only change is to step 8 of the construction procedure: the first
execution payload after a slot duration change scales its gas limit one time by
the slot-duration ratio, preserving the per-second gas throughput target. The
proposer's `target_gas_limit` does not alter this transition. Let
`parent_execution_payload_slot` be the slot of the beacon block associated with
the known execution payload identified by `bid.parent_block_hash`.

8. Set `bid.gas_limit` to be the gas limit of the constructed payload. If
   `get_slot_duration_ms(compute_epoch_at_slot(bid.slot))` differs from
   `get_slot_duration_ms(compute_epoch_at_slot(parent_execution_payload_slot))`,
   the gas limit MUST equal `parent_gas_limit` scaled by the ratio of the two
   durations (rounding down); otherwise, it MUST satisfy the inherited
   `is_gas_limit_target_compatible(parent_gas_limit, bid.gas_limit, target_gas_limit)`
   rule.
