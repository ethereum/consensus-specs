# EIP-8198 -- Honest Builder

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Builder activities](#builder-activities)
  - [Constructing the `SignedExecutionPayloadBid`](#constructing-the-signedexecutionpayloadbid)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an honest builder
to implement EIP-8198.

## Builder activities

### Constructing the `SignedExecutionPayloadBid`

Step 8 of the inherited construction procedure is modified. Let
`parent_execution_payload_slot` be the slot of the beacon block associated with
the known execution payload identified by `bid.parent_block_hash`. The builder
obtains this association from its fork-choice view.

- If `parent_execution_payload_slot` is before the first EIP-8198 slot and
  `bid.slot` is at or after it, the constructed payload's gas limit, and
  therefore `bid.gas_limit`, MUST equal
  `parent_gas_limit * SLOT_DURATION_MS_EIP8198 // SLOT_DURATION_MS`. The
  proposer's `target_gas_limit` does not alter this one-time transition.
- Otherwise, set `bid.gas_limit` to the constructed payload's gas limit, which
  MUST satisfy the inherited
  `is_gas_limit_target_compatible(parent_gas_limit, bid.gas_limit, target_gas_limit)`
  rule.

This rule is keyed to the parent *execution payload*, not merely the parent
beacon block. Therefore, if slots or execution payloads are missed around the
fork, the first eventual post-fork execution payload still performs the scaling
exactly once. The EIP-8198 networking document defines the executable helper
used for gossip validation of the same condition.
