# EIP-XXXX -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Presets](#presets)
  - [Type-specific SSZ bounds](#type-specific-ssz-bounds)
- [Helpers](#helpers)
  - [Modified `compute_fork_version`](#modified-compute_fork_version)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [Modified `execution_payload`](#modified-execution_payload)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
    - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
    - [ExecutionPayloadEnvelopesByRange v1](#executionpayloadenvelopesbyrange-v1)
    - [ExecutionPayloadEnvelopesByRoot v1](#executionpayloadenvelopesbyroot-v1)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-XXXX.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Presets

### Type-specific SSZ bounds

| Name                                            | Value                         |
| ----------------------------------------------- | ----------------------------- |
| `MAX_SIGNED_EXECUTION_PAYLOAD_BID_SIZE_EIPXXXX` | `Uint64(196966)` (= ~192 KiB) |

## Helpers

### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIPXXXX_FORK_EPOCH:
        return EIPXXXX_FORK_VERSION
    if epoch >= HEZE_FORK_EPOCH:
        return HEZE_FORK_VERSION
    if epoch >= GLOAS_FORK_EPOCH:
        return GLOAS_FORK_VERSION
    if epoch >= FULU_FORK_EPOCH:
        return FULU_FORK_VERSION
    if epoch >= ELECTRA_FORK_EPOCH:
        return ELECTRA_FORK_VERSION
    if epoch >= DENEB_FORK_EPOCH:
        return DENEB_FORK_VERSION
    if epoch >= CAPELLA_FORK_EPOCH:
        return CAPELLA_FORK_VERSION
    if epoch >= BELLATRIX_FORK_EPOCH:
        return BELLATRIX_FORK_VERSION
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

## The gossip domain: gossipsub

### Topics and messages

#### Global topics

##### Modified `execution_payload`

*Note*: The only change is a check that `envelope.inclusion_claims` matches
`bid.inclusion_claims_root`.

```python
def validate_execution_payload_envelope_gossip(
    seen: Seen,
    store: Store,
    signed_execution_payload_envelope: SignedExecutionPayloadEnvelope,
) -> None:
    """
    Validate a SignedExecutionPayloadEnvelope for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    envelope = signed_execution_payload_envelope.message
    payload = envelope.payload
    block_root = envelope.beacon_block_root

    # [IGNORE] The node has not seen another valid envelope for this block root from this builder
    envelope_key = (block_root, envelope.builder_index)
    if envelope_key in seen.execution_payload_envelopes:
        raise GossipIgnore("already seen envelope for this block root from this builder")

    # [IGNORE] The envelope's block root has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    if block_root not in store.blocks:
        raise GossipIgnore("envelope's block has not been seen")

    # [REJECT] The envelope's block passes validation
    if block_root not in store.block_states:
        raise GossipReject("envelope's block failed validation")

    state = store.block_states[block_root]

    # [IGNORE] The envelope is from a slot greater than or equal to the latest finalized slot
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    if payload.slot_number < finalized_slot:
        raise GossipIgnore("envelope is from a slot before the latest finalized slot")

    block = store.blocks[block_root]
    bid = block.body.signed_execution_payload_bid.message

    # [REJECT] The block's slot matches the payload's slot number
    if block.slot != payload.slot_number:
        raise GossipReject("block's slot does not match payload's slot number")

    # [REJECT] The envelope is from the builder committed to by the bid
    if envelope.builder_index != bid.builder_index:
        raise GossipReject("envelope's builder index does not match the bid's builder index")

    # [REJECT] The payload's block hash matches the bid's block hash
    if payload.block_hash != bid.block_hash:
        raise GossipReject("payload's block hash does not match the bid's block hash")

    # [REJECT] The envelope's execution requests root matches the bid's execution requests root
    if hash_tree_root(envelope.execution_requests) != bid.execution_requests_root:
        raise GossipReject("envelope's execution requests root does not match the bid's")

    # [New in EIPXXXX]
    # [REJECT] The envelope's inclusion claims root matches the bid's inclusion claims root
    if hash_tree_root(envelope.inclusion_claims) != bid.inclusion_claims_root:
        raise GossipReject("envelope's inclusion claims root does not match the bid's")

    # [REJECT] The execution request counts are within their limits
    verify_execution_requests_limits(envelope.execution_requests)

    # [REJECT] The number of withdrawals is within the limit
    if len(payload.withdrawals) > MAX_WITHDRAWALS_PER_PAYLOAD:
        raise GossipReject("too many withdrawals")

    # [REJECT] The envelope signature is valid
    if not verify_execution_payload_envelope_signature(state, signed_execution_payload_envelope):
        raise GossipReject("invalid envelope signature")

    # Mark this envelope as seen and store its payload
    seen.execution_payload_envelopes.add(envelope_key)
    seen.execution_payloads[payload.block_hash] = payload
```

## The Req/Resp domain

### Messages

#### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

The EIP-XXXX fork-digest is introduced to the `context` enum to specify the
EIP-XXXX beacon block type.

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `ELECTRA_FORK_VERSION`   | `electra.SignedBeaconBlock`   |
| `FULU_FORK_VERSION`      | `fulu.SignedBeaconBlock`      |
| `GLOAS_FORK_VERSION`     | `gloas.SignedBeaconBlock`     |
| `HEZE_FORK_VERSION`      | `heze.SignedBeaconBlock`      |
| `EIPXXXX_FORK_VERSION`   | `eipxxxx.SignedBeaconBlock`   |

#### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

The EIP-XXXX fork-digest is introduced to the `context` enum to specify the
EIP-XXXX beacon block type.

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `ELECTRA_FORK_VERSION`   | `electra.SignedBeaconBlock`   |
| `FULU_FORK_VERSION`      | `fulu.SignedBeaconBlock`      |
| `GLOAS_FORK_VERSION`     | `gloas.SignedBeaconBlock`     |
| `HEZE_FORK_VERSION`      | `heze.SignedBeaconBlock`      |
| `EIPXXXX_FORK_VERSION`   | `eipxxxx.SignedBeaconBlock`   |

#### ExecutionPayloadEnvelopesByRange v1

**Protocol ID:**
`/eth2/beacon_chain/req/execution_payload_envelopes_by_range/1/`

EIP-XXXX changes the SSZ type of `SignedExecutionPayloadEnvelope` through the
`inclusion_claims` field. Per `fork_version = compute_fork_version(epoch)`:

<!-- eth_consensus_specs: skip -->

| `fork_version`         | Chunk SSZ type                           |
| ---------------------- | ---------------------------------------- |
| `GLOAS_FORK_VERSION`   | `gloas.SignedExecutionPayloadEnvelope`   |
| `HEZE_FORK_VERSION`    | `heze.SignedExecutionPayloadEnvelope`    |
| `EIPXXXX_FORK_VERSION` | `eipxxxx.SignedExecutionPayloadEnvelope` |

#### ExecutionPayloadEnvelopesByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/execution_payload_envelopes_by_root/1/`

The response context table is identical to
[ExecutionPayloadEnvelopesByRange v1](#executionpayloadenvelopesbyrange-v1).
