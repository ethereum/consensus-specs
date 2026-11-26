# Daisugi -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `compute_fork_version`](#modified-compute_fork_version)
  - [`compute_fork_digest`](#compute_fork_digest)
- [Configuration](#configuration)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [Modified `beacon_block`](#modified-beacon_block)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
    - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
Daisugi.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes the
[Electra networking specification](../../electra/p2p-interface.md) as
pre-requisite.

## Helpers

### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    # [New in Daisugi]
    if epoch >= DAISUGI_FORK_EPOCH:
        return DAISUGI_FORK_VERSION
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

### `compute_fork_digest`

*Note*: `compute_fork_digest` is unchanged from Phase 0. Fulu is not part of
Daisugi's history, so the Daisugi fork digest is the first four bytes of
`compute_fork_data_root(DAISUGI_FORK_VERSION, genesis_validators_root)`, without
the Fulu blob-parameter mix-in.

## Configuration

*Note*: A Daisugi block can carry up to `MAX_RECURSIVE_STARK_PROOF_BYTES` (8
MiB) of proof on top of its transactions, which can exceed the default
`MAX_PAYLOAD_SIZE` of 10 MiB. Daisugi networks must raise `MAX_PAYLOAD_SIZE`;
`daisugi-devnet-0` uses `20971520` (20 MiB).

## The gossip domain: gossipsub

### Topics and messages

Topics follow the same specification as in prior upgrades. The derivation of the
`message-id` remains stable.

#### Global topics

##### Modified `beacon_block`

The `beacon_block` topic carries Daisugi `SignedBeaconBlock` messages from the
Daisugi fork on. The gossip validation conditions are unchanged from Electra.

*Note*: The EIP-8288 block hash commitment (see
[`is_valid_block_hash`](./beacon-chain.md#modified-is_valid_block_hash)) is
checked during block import, after gossip propagation, like an execution-layer
rejection. A block that fails it is rejected, but the peer that forwarded it is
not penalized.

## The Req/Resp domain

### Messages

#### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

The Daisugi fork-digest is introduced to the `context` enum to specify Daisugi
beacon block type.

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `ELECTRA_FORK_VERSION`   | `electra.SignedBeaconBlock`   |
| `DAISUGI_FORK_VERSION`   | `daisugi.SignedBeaconBlock`   |

*Note*: A node that rebuilds full Daisugi payloads from stored headers and
`engine_getPayloadBodiesByHash/ByRange` must check that
`hash_tree_root(body.recursive_stark_proof)` equals the stored header's
`recursive_stark_proof_root`, and must not serve the block if the proof is
missing or does not match.

#### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

The Daisugi fork-digest is introduced to the `context` enum to specify Daisugi
beacon block type.

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `ELECTRA_FORK_VERSION`   | `electra.SignedBeaconBlock`   |
| `DAISUGI_FORK_VERSION`   | `daisugi.SignedBeaconBlock`   |
