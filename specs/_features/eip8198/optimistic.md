# EIP-8198 -- Optimistic Sync

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Helpers](#helpers)
  - [Modified `current_slot`](#modified-current_slot)

<!-- mdformat-toc end -->

## Helpers

### Modified `current_slot`

Let `current_slot: Slot` be
`compute_slot_at_time_ms(Uint64(genesis_time), Uint64(time * 1000))`, where
`time` is the UNIX time according to the local system clock.

*Note*: This replaces the inherited genesis-anchored division by
`SLOT_DURATION_MS`. After `EIP8198_FORK_EPOCH`, optimistic import eligibility
uses the same piecewise slot-to-time mapping as fork choice, gossip validation,
and honest-validator scheduling.
