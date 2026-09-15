# EIP-8205 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in EIP-8205](#modifications-in-eip-8205)
  - [Helpers](#helpers)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
    - [Modified `verify_execution_requests_limits`](#modified-verify_execution_requests_limits)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [Modified `beacon_block`](#modified-beacon_block)
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
EIP-8205.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Modifications in EIP-8205

### Helpers

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIP8205_FORK_EPOCH:
        return EIP8205_FORK_VERSION
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

#### Modified `verify_execution_requests_limits`

*Note*: The function `verify_execution_requests_limits` is modified to also
enforce the per-payload preregistration request limit.

```python
def verify_execution_requests_limits(execution_requests: ExecutionRequests) -> None:
    """
    Verify that each execution request count is within its limit.
    Raises GossipReject on validation failure.
    """
    # [REJECT] The withdrawal request count is within the limit
    if len(execution_requests.withdrawals) > MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many withdrawal requests")

    # [REJECT] The consolidation request count is within the limit
    if len(execution_requests.consolidations) > MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many consolidation requests")

    # [REJECT] The builder deposit request count is within the limit
    if len(execution_requests.builder_deposits) > MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many builder deposit requests")

    # [REJECT] The builder exit request count is within the limit
    if len(execution_requests.builder_exits) > MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many builder exit requests")

    # [New in EIP8205]
    # [REJECT] The validator preregistration request count is within the limit
    if len(execution_requests.preregistrations) > MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many validator preregistration requests")
```

### The gossip domain: gossipsub

#### Topics and messages

##### Global topics

###### Modified `beacon_block`

The existing `validate_beacon_block_gossip` call to
`verify_execution_requests_limits(block.body.parent_execution_requests)` now
also enforces the per-payload preregistration request limit.

###### Modified `execution_payload`

The existing `validate_execution_payload_envelope_gossip` call to
`verify_execution_requests_limits(envelope.execution_requests)` now also
enforces the per-payload preregistration request limit. All other envelope
checks, including the bid's `execution_requests_root` commitment, remain
unchanged.

### The Req/Resp domain

#### Messages

##### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

The EIP-8205 fork-digest is introduced to the `context` enum to specify the
EIP-8205 beacon block type.

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
| `EIP8205_FORK_VERSION`   | `eip8205.SignedBeaconBlock`   |

##### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

The EIP-8205 fork-digest is introduced to the `context` enum to specify the
EIP-8205 beacon block type.

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
| `EIP8205_FORK_VERSION`   | `eip8205.SignedBeaconBlock`   |

##### ExecutionPayloadEnvelopesByRange v1

**Protocol ID:**
`/eth2/beacon_chain/req/execution_payload_envelopes_by_range/1/`

EIP-8205 changes the SSZ type of `SignedExecutionPayloadEnvelope` through the
`execution_requests` field. Per `fork_version = compute_fork_version(epoch)`:

<!-- eth_consensus_specs: skip -->

| `fork_version`         | Chunk SSZ type                           |
| ---------------------- | ---------------------------------------- |
| `GLOAS_FORK_VERSION`   | `gloas.SignedExecutionPayloadEnvelope`   |
| `HEZE_FORK_VERSION`    | `heze.SignedExecutionPayloadEnvelope`    |
| `EIP8205_FORK_VERSION` | `eip8205.SignedExecutionPayloadEnvelope` |

##### ExecutionPayloadEnvelopesByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/execution_payload_envelopes_by_root/1/`

The response context table is identical to
[ExecutionPayloadEnvelopesByRange v1](#executionpayloadenvelopesbyrange-v1).
