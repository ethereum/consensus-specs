# Peer Data Availability Sampling -- Core

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Custom types](#custom-types)
- [Configuration](#configuration)
  - [Data size](#data-size)
  - [Custody setting](#custody-setting)
  - [Helper functions](#helper-functions)
    - [`cycle`](#cycle)
    - [`get_custody_lines`](#get_custody_lines)
    - [Honest peer guide](#honest-peer-guide)
- [Custody](#custody)
    - [1. Custody](#1-custody)
      - [`CUSTODY_REQUIREMENT`](#custody_requirement)
      - [Public, deterministic selection](#public-deterministic-selection)
    - [2. Peer discovery](#2-peer-discovery)
    - [3. Row/Column gossip](#3-rowcolumn-gossip)
      - [Parameters](#parameters)
      - [Reconstruction and cross-seeding](#reconstruction-and-cross-seeding)
    - [4. Peer sampling](#4-peer-sampling)
    - [5. Peer scoring](#5-peer-scoring)
    - [6. DAS providers](#6-das-providers)
    - [7. A note on fork choice](#7-a-note-on-fork-choice)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `SampleIndex` | `uint64` | A sample index, corresponding to chunk of extended data |

## Configuration

### Data size

| Name | Value | Description |
| - | - | - |
| `NUMBER_OF_ROWS` | `uint64(2**4)` (= 32) | Number of rows in the 2D data array |
| `NUMBER_OF_COLUMNS` | `uint64(2**4)` (= 32) | Number of columns in the 2D data array |
| `DATA_PER_BLOB` | `FIELD_ELEMENTS_PER_BLOB * BYTES_PER_FIELD_ELEMENT` | Bytes |
| `DATA_PER_SLOT` | `MAX_BLOBS_PER_BLOCK * BLOB_SIZE * 4` | Bytes. Including the extension. |
| `DATA_PER_ROW` | `DATA_PER_SLOT / NUMBER_OF_ROWS` | |
| `DATA_PER_COLUMN` | `DATA_PER_SLOT / NUMBER_OF_COLUMNS` | |
| `DATA_PER_SAMPLE` | `DATA_PER_SLOT / (NUMBER_OF_COLUMNS * NUMBER_OF_ROWS)` |

### Custody setting

| Name | Value | Description |
| - | - | - |
| `SAMPLES_PER_SLOT` | `70` |
| `CUSTODY_REQUIREMENT` | `2` | |

### Helper functions

#### `cycle`
```python
def cycle(seq: Sequence[Any], start: int) -> Any:
    while True:
        yield seq[start]
        start = (start + 1) % len(seq)
```

#### `get_custody_lines`

```python
def get_custody_lines(node_id: int, epoch: int, custody_size: int, line_type: LineType) -> list[int]:
    bound = NUMBER_OF_ROWS if line_type else NUMBER_OF_COLUMNS
    all_items = list(range(bound))
    line_index = (node_id + epoch) % bound
    iterator = cycle(all_items, line_index)
    return [next(iterator) for _ in range(custody_size)]
```

#### Honest peer guide

## Custody


#### 1. Custody

##### `CUSTODY_REQUIREMENT`

Each node downloads and custodies a minimum of `CUSTODY_REQUIREMENT` rows and `CUSTODY_REQUIREMENT` columns per slot. The particular rows and columns that the node is required to custody are selected pseudo-randomly (more on this below).

A node *may* choose to custody and serve more than the minimum honesty requirement. Such a node explicitly advertises a number greater than `CUSTODY_REQUIREMENT`  via the peer discovery mechanism -- for example, in their ENR (e.g. `custody_lines: 8` if the node custodies `8` rows and `8` columns each slot) -- up to a maximum of `max(NUMBER_OF_ROWS, NUMBER_OF_COLUMNS)` (i.e. a super-full node).

A node stores the custodied rows/columns for the duration of the pruning period and responds to peer requests for samples on those rows/columns.

##### Public, deterministic selection 

The particular rows and columns that a node custodies are selected pseudo-randomly as a function of the node-id, epoch, and custody size (sample function interface: `get_custody_lines(config: Config, node_id: int, epoch: int, custody_size: int, line_type: LineType) -> list[int]` and column variant) -- importantly this function can be run by any party as the inputs are all public.

*Note*: `line_type` could be `LineType.ROW` or `LineType.COLUMN`.

*Note*: increasing the `custody_size` parameter for a given `node_id` and `epoch` extends the returned list (rather than being an entirely new shuffle) such that if `custody_size` is unknown, the default `CUSTODY_REQUIREMENT` will be correct for a subset of the node's custody.

*Note*: Even though this function accepts `epoch` as an input, the function can be tuned to remain stable for many epochs depending on network/subnet stability requirements. There is a trade-off between rigidity of the network and the depth to which a subnet can be utilized for recovery. To ensure subnets can be utilized for recovery, staggered rotation needs to happen likely on the order of the prune period.

#### 2. Peer discovery

At each slot, a node needs to be able to readily sample from *any* set of rows and columns. To this end, a node should find and maintain a set of diverse and reliable peers that can regularly satisfy their sampling demands.

A node runs a background peer discovery process, maintaining at least `NUMBER_OF_PEERS` of various custody distributions (both custody_size and row/column assignments). The combination of advertised `custody_size` size and public node-id make this readily, publicly accessible.

`NUMBER_OF_PEERS` should be tuned upward in the event of failed sampling.

*Note*: while high-capacity and super-full nodes are high value with respect to satisfying sampling requirements, a node should maintain a distribution across node capacities as to not centralize the p2p graph too much (in the extreme becomes hub/spoke) and to distribute sampling load better across all nodes.

*Note*: A DHT-based peer discovery mechanism is expected to be utilized in the above. The beacon-chain network currently utilizes discv5 in a similar method as described for finding peers of particular distributions of attestation subnets. Additional peer discovery methods are valuable to integrate (e.g. latent peer discovery via libp2p gossipsub) to add a defense in breadth against one of the discovery methods being attacked.

#### 3. Row/Column gossip

##### Parameters

There are both `NUMBER_OF_ROWS` row and `NUMBER_OF_COLUMNS` column gossip topics.

1. For each column -- `row_x` for `x` from `0` to `NUMBER_OF_COLUMNS` (non-inclusive). 
2. For each row -- `column_y` for `y` from `0` to `NUMBER_OF_ROWS` (non-inclusive).

To custody a particular row or column, a node joins the respective gossip subnet. Verifiable samples from their respective row/column are gossiped on the assigned subnet.


##### Reconstruction and cross-seeding

In the event a node does *not* receive all samples for a given row/column but does receive enough to reconstruct (e.g. 50%+, a function of coding rate), the node should reconstruct locally and send the reconstructed samples on the subnet.

Additionally, the node should send (cross-seed) any samples missing from a given row/column they are assigned to that they have obtained via an alternative method (ancillary gossip or reconstruction). E.g., if node reconstructs `row_x` and is also participating in the `column_y` subnet in which the `(x, y)` sample was missing, send the reconstructed sample to `column_y`.

*Note*: A node is always maintaining a matrix view of the rows and columns they are following, able to cross-reference and cross-seed in either direction.

*Note*: There are timing considerations to analyze -- at what point does a node consider samples missing and chooses to reconstruct and cross-seed.

*Note*: There may be anti-DoS and quality-of-service considerations around how to send samples and consider samples -- is each individual sample a message or are they sent in aggregate forms.

#### 4. Peer sampling

At each slot, a node makes (locally randomly determined) `SAMPLES_PER_SLOT` queries for samples from their peers. A node utilizes `get_custody_lines(..., line_type=LineType.ROW)`/`get_custody_lines(..., line_type=LineType.COLUMN)` to determine which peer(s) to request from. If a node has enough good/honest peers across all rows and columns, this has a high chance of success.

Upon sampling, the node sends an `DO_YOU_HAVE` packet for all samples to all peers who are determined to custody this sample according to their `get_custody_lines` results. All peers answer first with a bitfield of the samples that they have.

Upon receiving a sample, a node will pass on the sample to any node which did not previously have this sample, known by `DO_YOU_HAVE` response (but was supposed to have it according to its `get_custody_lines` results).

#### 5. Peer scoring

Due to the deterministic custody functions, a node knows exactly what a peer should be able to respond to. In the event that a peer does not respond to samples of their custodied rows/columns, a node may downscore or disconnect from a peer.

*Note*: a peer might not respond to requests either because they are dishonest (don't actually custody the data), because of bandwidth saturation (local throttling), or because they were, themselves, not able to get all the samples. In the first two cases, the peer is not of consistent DAS value and a node can/should seek to optimize for better peers. In the latter, the node can make local determinations based on repeated `DO_YOU_HAVE` queries to that peer and other peers to assess the value/honesty of the peer.

#### 6. DAS providers

A DAS provider is a consistently-available-for-DAS-queries, super-full (or high capacity) node. To the p2p, these look just like other nodes but with high advertised capacity, and they should generally be able to be latently found via normal discovery.

They can also be found out-of-band and configured into a node to connect to directly and prioritize. E.g., some L2 DAO might support 10 super-full nodes as a public good, and nodes could choose to add some set of these to their local configuration to bolster their DAS quality of service.

Such direct peering utilizes a feature supported out of the box today on all nodes and can complement (and reduce attackability) of alternative peer discovery mechanisms.

#### 7. A note on fork choice

The fork choice rule (essentially a DA filter) is *orthogonal to a given DAS design*, other than the efficiency of particular design impacting it.

In any DAS design, there are probably a few degrees of freedom around timing, acceptability of short-term re-orgs, etc. 

For example, the fork choice rule might require validators to do successful DAS on slot N to be able to include block of slot N in it's fork choice. That's the tightest DA filter. But trailing filters are also probably acceptable, knowing that there might be some failures/short re-orgs but that it doesn't hurt the aggregate security. E.g. The rule could be -- DAS must be completed for slot N-1 for a child block in N to be included in the fork choice.

Such trailing techniques and their analyiss will be valuable for any DAS construction. The question is — can you relax how quickly you need to do DA and in the worst case not confirm unavailable data via attestations/finality, and what impact does it have on short-term re-orgs and fast confirmation rules.
