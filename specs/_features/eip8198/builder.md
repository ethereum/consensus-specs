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
post-fork execution payload scales its gas limit one time by the slot-duration
ratio, preserving the per-second gas throughput target. The proposer's
`target_gas_limit` does not alter this transition. Let
`parent_execution_payload_slot` be the slot of the beacon block associated with
the known execution payload identified by `bid.parent_block_hash`.

8. Set `bid.gas_limit` to be the gas limit of the constructed payload. If
   `parent_execution_payload_slot < compute_start_slot_at_epoch(EIP8198_FORK_EPOCH) <= bid.slot`,
   the gas limit MUST equal
   `parent_gas_limit * SLOT_DURATION_MS_EIP8198 // SLOT_DURATION_MS`; otherwise,
   it MUST satisfy the inherited
   `is_gas_limit_target_compatible(parent_gas_limit, bid.gas_limit, target_gas_limit)`
   rule.
