# Fulu -- Peer Sampling

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helper functions](#helper-functions)
  - [`get_extended_sample_count`](#get_extended_sample_count)
- [Peer discovery](#peer-discovery)
- [Peer sampling](#peer-sampling)
  - [Sample selection](#sample-selection)
  - [Sample queries](#sample-queries)
- [Peer scoring](#peer-scoring)
- [DAS providers](#das-providers)

<!-- mdformat-toc end -->

## Introduction

The purpose of this document is to complement [Fulu -- Data Availability Sampling Core](das-core.md) by specifying the peer sampling functionality of the full PeerDAS protocol. Initially, this functionality may not be implemented by all clients. In such cases, it is replaced by [subnet sampling](das-core.md#subnet-sampling), which is an extension of the custody component of the protocol.

## Helper functions

### `get_extended_sample_count`

```python
def get_extended_sample_count(allowed_failures: uint64) -> uint64:
    assert 0 <= allowed_failures <= NUMBER_OF_COLUMNS // 2
    """
    Return the sample count if allowing failures.

    This helper demonstrates how to calculate the number of columns to query per slot when
    allowing given number of failures, assuming uniform random selection without replacement.
    Nested functions are direct replacements of Python library functions math.comb and
    scipy.stats.hypergeom.cdf, with the same signatures.
    """

    def math_comb(n: int, k: int) -> int:
        if not 0 <= k <= n:
            return 0
        r = 1
        for i in range(min(k, n - k)):
            r = r * (n - i) // (i + 1)
        return r

    def hypergeom_cdf(k: uint64, M: uint64, n: uint64, N: uint64) -> float:
        # Note: It contains float-point computations.
        # Convert uint64 to Python integers before computations.
        k = int(k)
        M = int(M)
        n = int(n)
        N = int(N)
        return sum([math_comb(n, i) * math_comb(M - n, N - i) / math_comb(M, N)
                    for i in range(k + 1)])

    worst_case_missing = NUMBER_OF_COLUMNS // 2 + 1
    false_positive_threshold = hypergeom_cdf(0, NUMBER_OF_COLUMNS,
                                             worst_case_missing, SAMPLES_PER_SLOT)
    for sample_count in range(SAMPLES_PER_SLOT, NUMBER_OF_COLUMNS + 1):
        if hypergeom_cdf(allowed_failures, NUMBER_OF_COLUMNS,
                         worst_case_missing, sample_count) <= false_positive_threshold:
            break
    return sample_count
```

## Peer discovery

At each slot, a node needs to be able to readily sample from *any* set of columns. To this end, a node SHOULD find and maintain a set of diverse and reliable peers that can regularly satisfy their sampling demands.

A node runs a background peer discovery process, maintaining peers of various custody distributions (both `custody_size` and column assignments). The combination of advertised `custody_size` size and public node-id make this readily and publicly accessible. The peer set should cover the whole column space, with some redundancy. The number of peers, or at least the redundancy implied by the custody distributions over the peer set, should be tuned upward in the event of failed sampling.

*Note*: while high-capacity and super-full nodes are high value with respect to satisfying sampling requirements, a node SHOULD maintain a distribution across node capacities as to not centralize the p2p graph too much (in the extreme becomes hub/spoke) and to distribute sampling load better across all nodes.

*Note*: A DHT-based peer discovery mechanism is expected to be utilized in the above. The beacon-chain network currently utilizes discv5 in a similar method as described for finding peers of particular distributions of attestation subnets. Additional peer discovery methods are valuable to integrate (e.g., latent peer discovery via libp2p gossipsub) to add a defense in breadth against one of the discovery methods being attacked.

## Peer sampling

### Sample selection

At each slot, a node SHOULD select at least `SAMPLES_PER_SLOT` column IDs for sampling. It is recommended to use uniform random selection without replacement based on local randomness. Sampling is considered successful if the node manages to retrieve all selected columns.

Alternatively, a node MAY use a method that selects more than `SAMPLES_PER_SLOT` columns while allowing some missing, respecting the same target false positive threshold (the probability of successful sampling of an unavailable block) as dictated by the `SAMPLES_PER_SLOT` parameter. If using uniform random selection without replacement, a node can use the `get_extended_sample_count(allowed_failures) -> sample_count` helper function to determine the sample count (number of unique column IDs) for any selected number of allowed failures. Sampling is then considered successful if any `sample_count - allowed_failures` columns are retrieved successfully.

For reference, the table below shows the number of samples and the number of allowed missing columns assuming `NUMBER_OF_COLUMNS = 128` and `SAMPLES_PER_SLOT = 16`.

| Allowed missing | 0| 1| 2| 3| 4| 5| 6| 7| 8|
|-----------------|--|--|--|--|--|--|--|--|--|
| Sample count    |16|20|24|27|29|32|35|37|40|

### Sample queries

A node SHOULD maintain a diverse set of peers for each column and each slot by verifying responsiveness to sample queries.

A node SHOULD query for samples from selected peers via `DataColumnSidecarsByRoot` request. A node utilizes `get_custody_groups` helper to determine which peer(s) it could request from, identifying a list of candidate peers for each selected column.

If more than one candidate peer is found for a given column, a node SHOULD randomize its peer selection to distribute sample query load in the network. Nodes MAY use peer scoring to tune this selection (for example, by using weighted selection or by using a cut-off threshold). If possible, it is also recommended to avoid requesting many columns from the same peer in order to avoid relying on and exposing the sample selection to a single peer.

If a node already has a column because of custody, it is not required to send out queries for that column.

If a node has enough good/honest peers across all columns, and the data is being made available, the above procedure has a high chance of success.

## Peer scoring

Due to the deterministic custody functions, a node knows exactly what a peer should be able to respond to. In the event that a peer does not respond to samples of their custodied rows/columns, a node may downscore or disconnect from a peer.

## DAS providers

A DAS provider is a consistently-available-for-DAS-queries, super-full (or high capacity) node. To the p2p, these look just like other nodes but with high advertised capacity, and they should generally be able to be latently found via normal discovery.

DAS providers can also be found out-of-band and configured into a node to connect to directly and prioritize. Nodes can add some set of these to their local configuration for persistent connection to bolster their DAS quality of service.

Such direct peering utilizes a feature supported out of the box today on all nodes and can complement (and reduce attackability and increase quality-of-service) alternative peer discovery mechanisms.
