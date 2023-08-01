# ePBS -- Networking


This document contains the consensus-layer networking specification for ePBS.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Table of contents

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork of ePBS to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The `beacon_block` topic is modified to also support block with bid and new topics are added per table below.

The derivation of the `message-id` remains stable.

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name | Message Type |
| - | - |
| `builder_bid` | `SignedBuilderBid`|
| `execution_payload` | `ExecutionPayload`|
| `execution_attestation` | `ExecutionAttestation` [New in ePBS]

##### Global topics

ePBS introduces new global topics for blob sidecars.

###### `beacon_block`

The *type* of the payload of this topic changes to the (modified) `SignedBeaconBlockWithBid` found in ePBS spec. Specifically, this type changes with the replacement of `SignedBuilderBid` to the inner `BeaconBlockBody`.

In addition to the gossip validations for this topic from prior specifications, the following validations MUST pass before forwarding the `signed_beacon_block` on the network. Alias `block = signed_beacon_block.message`, `signed_bid = block.body.signed_builder_bid`, `bid = signed_bid.message`, `header = bid.header`.


New validation:

- _[REJECT]_ The block's execution header timestamp is correct with respect to the slot -- i.e. `header.timestamp == compute_timestamp_at_slot(state, block.slot)`.
- _[REJECT]_ The bid pubkey is a valid builder in state.
- _[REJECT]_ The builder has sufficient balances to pay for the bid.
- _[REJECT]_ The builder signature, `signed_bid.signature`, is valid with respect to the `bid.pubkey`.

###### `execution_payload`

This topic is used to propagate execution payload.

The following validations MUST pass before forwarding the `execution_payload` on the network, assuming the alias `payload = execution_payload`:

- _[IGNORE]_ The payload aligns with header that received in block.

###### `execution_attestation`

This topic is used to propagate signed execution attestation.

The following validations MUST pass before forwarding the `execution_attestation` on the network, assuming the alias `data = execution_attestation.data`:

- _[IGNORE]_ `data.slot` is within the last `ATTESTATION_PROPAGATION_SLOT_RANGE` slots (within a MAXIMUM_GOSSIP_CLOCK_DISPARITY allowance) -- i.e. `data.slot + ATTESTATION_PROPAGATION_SLOT_RANGE >= current_slot >= data.slot` (a client MAY queue future attestations for processing at the appropriate slot).
- _[REJECT]_ The validator index is within the execution committee in `get_execution_committee(state, data.slot)`
- _[IGNORE]_ The execution payload being voted for (`data.execution_hash`) has been seen (via both gossip and non-gossip sources) (a client MAY queue execution attestations for processing once payload is retrieved).
- _[REJECT]_ The signature of `execution_attestation` is valid.

###### `builder_bid`

This topic is used to propagate signed builder bids.

The following validations MUST pass before forwarding the `signed_builder_bid` on the network, assuming the alias `bid = signed_builder_bid.message`:

- _[REJECT]_ The signed builder bid pubkey, `bid.pubkey`, exists in state.
- _[IGNORE]_ The signed builder bid value, `bid.value`, is less than builder's balance in state.
- _[IGNORE]_ The signed builder header timestamp is correct with respect to next slot -- i.e. `header.timestamp == compute_timestamp_at_slot(state, current_slot + 1)`.
- _[IGNORE]_ The signed builder header parent block has matches one of the chain tip in the fork choice store. Builder may submit multiple bids with respect to forks.
- _[REJECT]_ The builder signature, `signed_bid.signature`, is valid with respect to the `bid.pubkey`.

#### Transitioning the gossip

See gossip transition details found in the [Altair document](../altair/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics for this upgrade.

### The Req/Resp domain

#### Messages

##### ExecutionPayloadByHash v1

**Protocol ID:** `/eth2/beacon_chain/req/execution_payload_by_hash/1/`

The `<context-bytes>` field is calculated as `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`           | Chunk SSZ type                |
|--------------------------|-------------------------------|
| `EPBS_FORK_VERSION`     | `epbs.EXECUTION_PAYLOAD`           |

Request Content:

```
(
  List[HASH, MAX_REQUEST_PAYLOAD]
)
```

Response Content:

```
(
  List[EXECUTION_PAYLOAD, MAX_REQUEST_PAYLOAD]
)
```


## Design decision rationale

TODO: Add