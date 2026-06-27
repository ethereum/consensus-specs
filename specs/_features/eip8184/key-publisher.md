# EIP-8184 -- Honest Key Publisher

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Becoming a key publisher](#becoming-a-key-publisher)
- [Key publisher activities](#key-publisher-activities)
  - [Observing ST-commitments](#observing-st-commitments)
  - [Verifying the gas obligation budget](#verifying-the-gas-obligation-budget)
  - [Verifying ordering against `max_preceding_commitments`](#verifying-ordering-against-max_preceding_commitments)
  - [Waiting for attestation confirmation](#waiting-for-attestation-confirmation)
  - [Releasing the `LucidKeyMessage`](#releasing-the-lucidkeymessage)
- [Liability for non-reveal](#liability-for-non-reveal)

<!-- mdformat-toc end -->

## Introduction

A *key publisher* is an off-protocol actor that holds DEM keys for sealed
transactions and releases them after the scheduling decision is fixed.
Key publishers are not validators and do not have any in-protocol
registration in this version of LUCID. A sealed transaction's
`key_publisher` field is an execution-layer address; for bundles, the
`SealedBundle.key_publisher_signature` recovers the publisher's address
over `(chain_id, bundle_root)`.

Key publishers may be the senders themselves (trustless self-decryption),
or independent parties that sign bundles on behalf of multiple senders.

*Note*: This document specifies the *honest* behaviour of a key
publisher. It is provided for client implementers building tooling for
key publishers, not as in-protocol enforcement.

## Becoming a key publisher

There is no in-protocol registration. A key publisher publishes its
existence and encryption instructions out-of-band. Senders direct sealed
transactions to a key publisher by setting `ticket.key_publisher` to its
address (and, for bundles, by including the ticket in a bundle the
publisher signs).

*Note*: Discovery, reputation, and trust registries (for example, the
trust graph sketched in EIP-8105) are out of scope for this version of
LUCID.

## Key publisher activities

### Observing ST-commitments

Upon observing a beacon block at slot `t`, a key publisher inspects
`block.body.signed_execution_payload_bid.message.st_commitments` for any
commitment whose `commitment_key` matches a key it holds. For each such
commitment, the publisher proceeds with the verification steps below.

### Verifying the gas obligation budget

The key publisher MUST verify:

1. For its own commitment, that `commitment.gas_obligation` correctly
   equals the aggregate `ticket.gas_limit` of the bundle members with
   `executable[i] == 1` (or the ticket's `gas_limit` for a non-bundle
   commitment).
2. That the aggregate `gas_obligation` across *all* commitments in
   `bid.st_commitments` is within `compute_tob_gas_limit(bid.gas_limit)`.

If either check fails, the publisher MUST NOT release its key for this
commitment — the commitment is invalid and the payload will be rejected.

### Verifying ordering against `max_preceding_commitments`

The publisher MUST verify that its commitment's position in
`bid.st_commitments` (as determined by
[`is_valid_st_commitment_ordering`](./beacon-chain.md#new-is_valid_st_commitment_ordering))
is consistent with the `max_preceding_commitments` field of the
underlying sealed ticket(s). If any committed ticket would execute at a
position exceeding its `max_preceding_commitments`, the publisher MUST
NOT release the key.

### Waiting for attestation confirmation

The publisher SHOULD wait until the beacon block at slot `t` has been
attested to (e.g., observed in `state.current_epoch_participation` or
inferred from sufficient on-network attestations) before releasing the
key. This avoids releasing a key against a block that does not become
canonical.

### Releasing the `LucidKeyMessage`

The publisher constructs and broadcasts a `LucidKeyMessage` over the
`lucid_key_message` gossip topic, before
`get_lucid_key_message_due_ms()` milliseconds into slot `t+1`.

- Set `chain_id` to the local chain identifier.
- Set `scheduling_beacon_block_root` to `hash_tree_root(block)` of the
  scheduling beacon block.
- Set `scheduling_slot` to `block.slot`.
- Set `commit_index` to the index of the publisher's commitment within
  `bid.st_commitments`.
- Set `k_dems` to the list of DEM keys for the executable members of the
  commitment, in bundle order filtered to `executable[i] == 1`. For a
  non-bundle commitment, `k_dems` is a single-element list.

*Note*: For a single-ST commitment whose sender chooses to self-decrypt,
the sender may itself release the `LucidKeyMessage`, even if
`ticket.key_publisher` is set to another address.

## Liability for non-reveal

There is no in-protocol mechanism by which a key publisher assumes
liability for bundle non-reveal in this version of LUCID. Liability for
the unrefunded portion of `tob_fee`
(`tob_fee // TOB_FEE_FRACTION`, with the remainder refunded to the
sender via the execution layer) is paid by the *sender* by default.

Key publishers may approximate publisher-borne liability out-of-protocol
by including a sponsor sealed transaction in the bundle as described in
the EIP-8184 Rationale (§"Key publisher liability for non-reveal"). The
in-protocol enforcement of publisher liability is left to a future
upgrade.
