# Data Availability Sampling -- Sampling

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Data Availability Sampling](#data-availability-sampling)
- [GossipSub](#gossipsub)
  - [Horizontal subnets](#horizontal-subnets)
  - [Vertical subnets](#vertical-subnets)
    - [Slow rotation: Backbone](#slow-rotation-backbone)
    - [Quick rotation: Sampling](#quick-rotation-sampling)
  - [DAS during network instability](#das-during-network-instability)
    - [Stage 0: Waiting on missing samples](#stage-0-waiting-on-missing-samples)
    - [Stage 1: Pulling missing samples from known peers](#stage-1-pulling-missing-samples-from-known-peers)
    - [Stage 2: Pulling missing data from validators with custody.](#stage-2-pulling-missing-data-from-validators-with-custody)

<!-- mdformat-toc end -->

## Data Availability Sampling

TODO: Summary of Data Availability problem

TODO: Summary of solution, why 2x extension, and randomized samples

## GossipSub

### Horizontal subnets

TODO

### Vertical subnets

#### Slow rotation: Backbone

TODO

#### Quick rotation: Sampling

TODO

### DAS during network instability

The GossipSub based retrieval of samples may not always work.
In such event, a node can move through below stages until it recovers data availability.

#### Stage 0: Waiting on missing samples

Wait for the sample to re-broadcast. Someone may be slow with publishing, or someone else is able to do the work.

Any node can do the following work to keep the network healthy:
- Common: Listen on a horizontal subnet, chunkify the block data in samples, and propagate the samples to vertical subnets.
- Extreme: Listen on enough vertical subnets, reconstruct the missing samples by recovery, and propagate the recovered samples.

This is not a requirement, but should improve the network stability with little resources, and without any central party.

#### Stage 1: Pulling missing samples from known peers

The more realistic option, to execute when a sample is missing, is to query any node that is known to hold it.
Since *consensus identity is disconnected from network identity*, there is no direct way to contact custody holders
without explicitly asking for the data.

However, *network identities* are still used to build a backbone for each vertical subnet.
These nodes should have received the samples, and can serve a buffer of them on demand.
Although serving these is not directly incentivised, it is little work:
1. Buffer any message you see on the backbone vertical subnets, for a buffer of up to two weeks.
2. Serve the samples on request. An individual sample is just expected to be `~ 0.5 KB`, and does not require any pre-processing to serve.

A validator SHOULD make a `DASQuery` request to random peers, until failing more than the configured failure-rate.

TODO: detailed failure-mode spec. Stop after trying e.g. 3 peers for any sample in a configured time window (after the gossip period).

#### Stage 2: Pulling missing data from validators with custody.

Pulling samples directly from nodes with validators that have a custody responsibility,
without revealing their identity to the network, is an open problem.

