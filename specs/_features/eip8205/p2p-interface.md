# EIP-8205 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in EIP-8205](#modifications-in-eip-8205)
  - [Helpers](#helpers)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
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
