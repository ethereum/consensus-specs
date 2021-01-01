# Ethereum 2.0 Phase 1 -- Network specification for Data Availability Sampling 

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

<!-- /TOC -->

## Introduction

For an introduction about DAS itself, see [the DAS section in the Phase 1 validator spec](./validator.md#data-availability-sampling).
This is not a pre-requisite for the network layer, but will give you valuable context. 

For sampling, all nodes need to query for `k` random samples each slot.

*__TODO__: describe big picture of sampling workload size*

This is a lot of work, and ideally happens at a low latency.

To achieve quick querying, the query model is changed to *push* the samples to listeners instead, using GossipSub.
The listeners then randomly rotate their subscriptions to keep queries unpredictable.
Except for a small subset of subscriptions, which will function as a backbone to keep topics more stable.

Publishing can utilize the fan-out functionality in GossipSub, and is easier to split between nodes:
nodes on the horizontal networks can help by producing the same samples and fan-out publishing to their own peers.

This push model also helps to obfuscate the original source of a message:
the listeners will not have to make individual queries to some identified source.

The push model does not aim to serve "historical" queries (anything older than the most recent).
Historical queries are still required for the unhappy case, where messages are not pushed quick enough,
and missing samples are not reconstructed by other nodes on the horizontal subnet quick enough.

The main challenge in supporting historical queries is to target the right nodes, 
without concentrating too many requests on a single node, or breaking the network/consensus identity separation.

## DAS Subnets

On a high level, the push-model roles are divided into:
- Sources: create blobs of shard block data, and transformed into many tiny samples. 
- Sinks: continuously look for samples

At full operation, the network has one proposer, per shard, per slot.

In the push-model, there are:
- *Vertical subnets*: Sinks can subscribe to indices of samples: there is a sample to subnet mapping.
- *Horizontal subnets*: Sources need to distribute samples to all vertical networks: they participate in a fanout layer.

### Horizontal subnets

The shift of the distribution responsibility to a proposer can only be achieved with amplification:
a regular proposer cannot reach every vertical subnet.

#### Publishing

To publish their work, proposers already put the shard block as a whole on a shard-block subnet.

The proposer can fan-out their work more aggressively, by using the fan-out functionality of GossipSub:
it may publish to all its peers on the subnet, instead of just those in its mesh.

#### Horizontal propagation

Peers on the horizontal subnet are expected to at least perform regular propagation of shard blocks, like how do would participate in any other topic.

*Although this may be sufficient for testnets, expect parameter changes in the spec here.*

#### Horizontal to vertical

Nodes on this same subnet can replicate the sampling efficiently (including a proof for each sample),
and distribute it to any vertical networks that are available to them.

Since the messages are content-addressed (instead of origin-stamped), 
multiple publishers of the same samples on a vertical subnet do not hurt performance, 
but actually improve it by shortcutting regular propagation on the vertical subnet, and thus lowering the latency to a sample.


### Vertical subnets

Vertical subnets propagate the samples to every peer that is interested.
These interests are randomly sampled and rotate quickly: although not perfect, 
sufficient to avoid any significant amount of nodes from being 100% predictable.

As soon as a sample is missing after the expected propagation time window,
nodes can divert to the pull-model, or ultimately flag it as unavailable data.

#### Slow rotation: Backbone

To allow for subscriptions to rotate quickly and randomly, a backbone is formed to help onboard peers into other topics.

This backbone is based on a pure function of the *node* identity and time:
- Nodes can be found *without additional discovery overhead*:
  peers on a vertical topic can be found by searching the local peerstore for identities that hash to the desired topic(s). 
- Nodes can be held accountable for contributing to the backbone:
  peers that particpate in DAS but are not active on the appropriate backbone topics can be scored down.

A node should anticipate backbone topics to subscribe to based their own identity.
These subscriptions rotate slowly, and with different offsets per node identity to avoid sudden network-wide rotations.

```python
# TODO hash function: (node, time)->subnets
```

Backbone subscription work is outlined in the [DAS validator spec](./validator.md#data-availability-sampling)

#### Quick Rotation: Sampling

A node MUST maintain `k` random subscriptions to topics, and rotate these according to the [DAS validator spec](./validator.md#data-availability-sampling).
If the node does not already have connected peers on the topic it needs to sample, it can search its peerstore for peers in the topic backbone.

## DAS in the Gossip domain: Push

### Topics and messages

#### Horizontal subnets



#### Vertical subnets



## DAS in the Req-Resp domain: Pull

To pull samples from nodes, in case of network instability when samples are unavailable, a new query method is added to the Req-Resp domain.

This builds on top of the protocol identification and encoding spec which was introduced in [the Phase0 network spec](../phase0/p2p-interface.md). 

Note that the Phase1 DAS networking uses a different protocol prefix: `/eth2/das/req`

The result codes are extended with:
-  3: **ResourceUnavailable** -- when the request was valid but cannot be served at this point in time.

TODO: unify with phase0? Lighthoue already defined this in their response codes enum.

### Messages

#### DASQuery

**Protocol ID:** `/eth2/das/req/query/1/`

Request Content:
```
(
  sample_index: SampleIndex
)
```

Response Content:
```
(
  DASSample
)
```

When the sample is:
- Available: respond with a `Success` result code, and the encoded sample.
- Expected to be available, but not: respond with a `ResourceUnavailable` result code.
- Not available, but never of interest to the node: respond with an `InvalidRequest` result code.

When the node is part of the backbone and expected to have the sample, the validity of the quest MUST be recognized with `Success` or `ResourceUnavailable`.
