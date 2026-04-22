# Bellatrix -- Networking

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in Bellatrix](#modifications-in-bellatrix)
  - [Types](#types)
  - [Constants](#constants)
  - [Helpers](#helpers)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
    - [Transitioning the gossip](#transitioning-the-gossip)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
      - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
- [Gossipsub](#gossipsub)
  - [Why was the max gossip message size increased at Bellatrix?](#why-was-the-max-gossip-message-size-increased-at-bellatrix)
  - [Req/Resp](#reqresp)
    - [Why was the max chunk response size increased at Bellatrix?](#why-was-the-max-chunk-response-size-increased-at-bellatrix)
    - [Why allow invalid payloads on the P2P network?](#why-allow-invalid-payloads-on-the-p2p-network)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
Bellatrix.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite. This
document should be viewed as additive to the documents from
[Phase 0](../phase0/p2p-interface.md) and from
[Altair](../altair/p2p-interface.md) and will be referred to as the "Phase 0
document" and "Altair document" respectively, hereafter. Readers should
understand the Phase 0 and Altair documents and use them as a basis to
understand the changes outlined in this document.

## Modifications in Bellatrix

### Types

| Name                      | SSZ equivalent | Description                                     |
| ------------------------- | -------------- | ----------------------------------------------- |
| `PayloadValidationStatus` | `uint8`        | Execution payload validation status for a block |

### Constants

| Name                           | Value                        |
| ------------------------------ | ---------------------------- |
| `PAYLOAD_STATUS_VALID`         | `PayloadValidationStatus(0)` |
| `PAYLOAD_STATUS_INVALIDATED`   | `PayloadValidationStatus(1)` |
| `PAYLOAD_STATUS_NOT_VALIDATED` | `PayloadValidationStatus(2)` |

### Helpers

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= BELLATRIX_FORK_EPOCH:
        return BELLATRIX_FORK_VERSION
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

### The gossip domain: gossipsub

Some gossip meshes are upgraded in Bellatrix to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades. All topics remain
stable except the beacon block topic which is updated with the modified type.

The specification around the creation, validation, and dissemination of messages
has not changed from the Phase 0 and Altair documents unless explicitly noted
here.

The derivation of the `message-id` remains stable.

The new topics along with the type of the `data` field of a gossipsub message
are given in this table:

| Name           | Message Type                   |
| -------------- | ------------------------------ |
| `beacon_block` | `SignedBeaconBlock` (modified) |

Note that the `ForkDigestValue` path segment of the topic separates the old and
the new `beacon_block` topics.

##### Global topics

Bellatrix changes the type of the global beacon block topic.

###### `beacon_block`

The `beacon_block` topic is used solely for propagating new signed beacon blocks
to all nodes on the networks. Signed blocks are sent in their entirety. The
`state` parameter is the head state.

*Note*: Blocks with execution enabled will be permitted to propagate regardless
of the validity of the execution payload. This prevents network segregation
between [optimistic](../../sync/optimistic.md) and non-optimistic nodes.

```python
def validate_beacon_block_gossip(
    seen: Seen,
    store: Store,
    state: BeaconState,
    signed_beacon_block: SignedBeaconBlock,
    current_time_ms: uint64,
    # [New in Bellatrix]
    block_payload_statuses: Dict[Root, PayloadValidationStatus] = {},
) -> None:
    """
    Validate a SignedBeaconBlock for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    block = signed_beacon_block.message
    execution_payload = block.body.execution_payload

    # [IGNORE] The block is not from a future slot
    # (MAY be queued for processing at the appropriate slot)
    if not is_not_from_future_slot(state, block.slot, current_time_ms):
        raise GossipIgnore("block is from a future slot")

    # [IGNORE] The block is from a slot greater than the latest finalized slot
    # (MAY choose to validate and store such blocks for additional purposes
    # -- e.g. slashing detection, archive nodes, etc).
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    if block.slot <= finalized_slot:
        raise GossipIgnore("block is not from a slot greater than the latest finalized slot")

    # [IGNORE] The block is the first block with valid signature received for the proposer for the slot
    if (block.proposer_index, block.slot) in seen.proposer_slots:
        raise GossipIgnore("block is not the first valid block for this proposer and slot")

    # [REJECT] The proposer index is a valid validator index
    if block.proposer_index >= len(state.validators):
        raise GossipReject("proposer index out of range")

    # [REJECT] The proposer signature is valid
    proposer = state.validators[block.proposer_index]
    domain = get_domain(state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(block.slot))
    signing_root = compute_signing_root(block, domain)
    if not bls.Verify(proposer.pubkey, signing_root, signed_beacon_block.signature):
        raise GossipReject("invalid proposer signature")

    # [IGNORE] The block's parent has been seen (via gossip or non-gossip sources)
    # (MAY be queued until parent is retrieved)
    if block.parent_root not in store.blocks:
        raise GossipIgnore("block's parent has not been seen")

    # [New in Bellatrix]
    if is_execution_enabled(state, block.body):
        # [REJECT] The block's execution payload timestamp is correct with respect to the slot
        if execution_payload.timestamp != compute_time_at_slot(state, block.slot):
            raise GossipReject("incorrect execution payload timestamp")

        parent_payload_status = PAYLOAD_STATUS_NOT_VALIDATED
        if block.parent_root in block_payload_statuses:
            parent_payload_status = block_payload_statuses[block.parent_root]

        if block.parent_root not in store.block_states:
            if parent_payload_status == PAYLOAD_STATUS_NOT_VALIDATED:
                # [REJECT] The block's parent passes validation
                raise GossipReject("block's parent failed validation (parent execution unknown)")

            # [IGNORE] The block's parent passes validation
            raise GossipIgnore("block's parent failed validation (parent execution known)")

        # [IGNORE] The block's parent's execution payload passes validation
        if parent_payload_status == PAYLOAD_STATUS_INVALIDATED:
            raise GossipIgnore("block's parent's execution payload failed validation")
    else:
        # [REJECT] The block's parent passes validation
        if block.parent_root not in store.block_states:
            # [Modified in Bellatrix]
            raise GossipReject("block's parent failed validation (execution disabled)")

    # [REJECT] The block is from a higher slot than its parent
    if block.slot <= store.blocks[block.parent_root].slot:
        raise GossipReject("block is not from a higher slot than its parent")

    # [REJECT] The current finalized checkpoint is an ancestor of the block
    checkpoint_block = get_checkpoint_block(
        store, block.parent_root, store.finalized_checkpoint.epoch
    )
    if checkpoint_block != store.finalized_checkpoint.root:
        raise GossipReject("finalized checkpoint is not an ancestor of block")

    # [REJECT] The block is proposed by the expected proposer for the slot
    # (if shuffling is not available, IGNORE instead and MAY be queued for later)
    parent_state = store.block_states[block.parent_root].copy()
    process_slots(parent_state, block.slot)
    expected_proposer = get_beacon_proposer_index(parent_state)
    if block.proposer_index != expected_proposer:
        raise GossipReject("block proposer_index does not match expected proposer")

    # Mark this block as seen for this proposer/slot combination
    seen.proposer_slots.add((block.proposer_index, block.slot))
```

#### Transitioning the gossip

See gossip transition details found in the
[Altair document](../altair/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics.

### The Req/Resp domain

Non-faulty, [optimistic](../../sync/optimistic.md) nodes may send blocks which
result in an INVALID response from an execution engine. To prevent network
segregation between optimistic and non-optimistic nodes, transmission of an
INVALID execution payload via the Req/Resp domain SHOULD NOT cause a node to be
down-scored or disconnected. Transmission of a block which is invalid due to any
consensus-layer rules (i.e., *not* execution-layer rules) MAY result in
down-scoring or disconnection.

#### Messages

##### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

Request and Response remain unchanged. Bellatrix fork-digest is introduced to
the `context` enum to specify Bellatrix block type.

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |

##### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

Request and Response remain unchanged. Bellatrix fork-digest is introduced to
the `context` enum to specify Bellatrix block type.

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |

# Design decision rationale

## Gossipsub

### Why was the max gossip message size increased at Bellatrix?

With the addition of `ExecutionPayload` to `BeaconBlock`s, there is a dynamic
field -- `transactions` -- which can validly exceed the `MAX_PAYLOAD_SIZE` limit
(1 MiB) put in place at Phase 0, so MAX_PAYLOAD_SIZE has increased to 10 MiB on
the network. At the `GAS_LIMIT` (~30M) currently seen on mainnet in 2021, a
single transaction filled entirely with data at a cost of 16 gas per byte can
create a valid `ExecutionPayload` of ~2 MiB. Thus we need a size limit to at
least account for current mainnet conditions.

Note, that due to additional size induced by the `BeaconBlock` contents (e.g.
proposer signature, operations lists, etc) this does reduce the theoretical max
valid `ExecutionPayload` (and `transactions` list) size as slightly lower than
10 MiB. Considering that `BeaconBlock` max size is on the order of 128 KiB in
the worst case and the current gas limit (~30M) bounds max blocksize to less
than 2 MiB today, this marginal difference in theoretical bounds will have zero
impact on network functionality and security.

### Req/Resp

#### Why was the max chunk response size increased at Bellatrix?

Similar to the discussion about the maximum gossip size increase, the
`ExecutionPayload` type can cause `BeaconBlock`s to exceed the 1 MiB bounds put
in place during Phase 0.

As with the gossip limit, 10 MiB is selected because this is firmly above any
valid block sizes in the range of gas limits expected in the medium term.

As with both gossip and req/rsp maximum values, type-specific limits should
always by simultaneously respected.

#### Why allow invalid payloads on the P2P network?

The specification allows blocks with invalid execution payloads to propagate
across gossip and via RPC calls. The reasoning for this is as follows:

1. Optimistic nodes must listen to block gossip to obtain a view of the head of
   the chain.
2. Therefore, optimistic nodes must propagate gossip blocks. Otherwise, they'd
   be censoring.
3. If optimistic nodes will propagate blocks via gossip, then they must respond
   to requests for the parent via RPC.
4. Therefore, optimistic nodes must send optimistic blocks via RPC.

So, to prevent network segregation from optimistic nodes inadvertently sending
invalid execution payloads, nodes should never downscore/disconnect nodes due to
such invalid payloads. This does open the network to some DoS attacks from
invalid execution payloads, but the scope of actors is limited to validators who
can put those payloads in valid (and slashable) beacon blocks. Therefore, it is
argued that the DoS risk introduced in tolerable.

More complicated schemes are possible that could restrict invalid payloads from
RPC. However, it's not clear that complexity is warranted.
