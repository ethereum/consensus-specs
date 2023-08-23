# Recommendations for Gossipsub Parameters

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [General Gossipsub Parameters](#general-gossipsub-parameters)
  - [Gossipsub v1.0 General Parameters](#gossipsub-v10-general-parameters)
  - [Gossipsub v1.1 General Parameters](#gossipsub-v11-general-parameters)
- [General Scoring Parameters](#general-scoring-parameters)
  - [Thresholds](#thresholds)
  - [Scoring Parameters](#scoring-parameters)
- [Topic Specific Parameters](#topic-specific-parameters)
  - [Topics Parameters](#topics-parameters)
  - [Topic Score Parameters](#topic-score-parameters)
    - [Beacon Block Topic](#beacon-block-topic)
    - [Attestation Aggregate Topic](#attestation-aggregate-topic)
    - [Subnet and Sync Committee Topics](#subnet-and-sync-committee-topics)
    - [Other topics](#other-topics)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document provides a rough guideline for implementers to follow when
setting their Gossipsub parameters for an Eth2 network.

## General Gossipsub Parameters

This gives an overview of the general parameters, and expected values for the Ethereum 2.0 network. These help form the basic structure of the mesh network in Gossipsub and apply globally to all peers regardless of topic. These work regardless of whether scoring is enabled.

### Gossipsub v1.0 General Parameters

| Parameter | Value | Description |
| -------- | -------- | -------- |
| `d_low`  | 6     | Mesh maintenance - Finds more peers below this value |
| `d`      | 8     | Mesh maintenance - Target peers in the mesh|
| `d_high` | 12    | Mesh maintenance - Remove peers above this value|
| `d_lazy` | 6     | Minimum number of peers to gossip to (if they exist)|
| `heartbeat_interval` | 0.7 |  Frequency of heartbeat, in seconds | 
| `fanout_ttl` | 60 |  TTL for fanout maps for topics we are not subscribed to but have published to, seconds |
| `mcache_len` | 6 |  Number of heartbeats to retain full messages in cache for `IWANT` responses |
| `mcache_gossip` | 3 |  Number of heartbeats to gossip about|
| `seen_ttl` | 33 slots (396 seconds, 566 heartbeats | Amount of time to retain message IDs|

### Gossipsub v1.1 General Parameters

| Parameter | Value | Description |
| -------- | -------- | -------- |
| `prune_backoff`  | 1 min  | The amount of time a peer must wait before re-grafting to the mesh once being pruned |
| `flood_publish`  |  True  | When publishing a message we send to all known peers of a topic not just those in the mesh (this should help message propagation) |
| `gossip_factor`  |  0.25  | The factor of peers to gossip to during a round. With `D_lazy` as a minimum. [See here](https://github.com/libp2p/specs/blob/master/pubsub/gossipsub/gossipsub-v1.1.md#adaptive-gossip-dissemination) for further info |
| `D_score`    |  4     | When pruning the mesh due to oversubscription, we keep this many highest-scoring peers |
| `D_out`    |  2     | When pruning the mesh due to oversubscription, we keep this many outbound connected peers |
| `peers_in_px` | 16 |  The maximum number of alternate peers a peer can connect to when being pruned |
| `graft_flood_threshold` | 10 secs | Extra penalty if a peer grafts before this time |
| `ppportunistic_graft_ticks` | 85 | Number of heartbeats before attempting opportunistic grafting (this is where we look for better scored peers for our mesh) |
| `ppportunistic_graft_peers` | 2 |  Number of peers to opportunistically graft |
| `gossip_retransmission` | 3 | The maximum number of times we allow a peer to ask via IWANT for the same message id |
| `max_ihave_length` | 5000 |  The maximum number of message ids we send in an IHAVE gossip |
| `max_ihave_messages` | 5 | The maximum number of IHAVE messages we allow per peer per heartbeat |
| `iwant_follow_up_time` | 3 secs | The maximum amount of time a peer has to respond to an IWANT before being penalized |


## General Scoring Parameters

These parameters are general and apply to all peers regardless of topic. This are only used once scoring is enabled.

### Thresholds 
| Parameter | Value | Description |
| -------- | -------- | -------- |
| `gossip_threshold` | -4000 | If a peer has a score below this value we no longer gossip to or accept gossip from that peer |
| `publish_threshold` | -8000 | If a peer has a score below this value we no longer publish to that peer |
| `greylist_threshold` | -16000 | If a peer has a score below this value we no longer accept messages from the peer |
| `accept_px_threshold` | 100 | If a peer has a score below this value we no longer accept PX peers from their prunes |
| `opportunistic_graft_threshold` | 5 | If a peer has a score below this value we consider them for replacement via opportunistic grafting |
| `ip_colocation_threshold` | 10 | The number of peers allowed with the same IP. Peers exceeding this get quadratically penalized |

### Scoring Parameters

| Parameter | Value | Description |
| -------- | -------- | -------- |
| `decay_interval` | 1 Slot | The time interval in which to apply decays to scores |
| `decay_to_zero` | 0.1 | The minimum score before the next decay sets the score to 0 |
| `retain_score` | 100 epochs | The duration of time we remember scores for disconnected peers |
| `app_specific_weight` | 1 | Application can provide a score. We don't give it additional weighting |
| `ip_colocation_factor_weight` | -1 | The weighting assigned to penalize peers using the same IP |
| `behaviour_penality_weight` | -99 | Penalty for bad behaviours: Attempted to re-graft too early and not responding to IWANT messages in the `IWANT follow up time` |
| `behaviour_penalty_decay` | 0.928 | The decay rate for the behaviour penalty  |
| `topic_score_cap` | 32.72 | The maximum score a peer can attain from topic scores |

## Topic Specific Parameters

These are parameters that apply to each specific topic. This section provides an overview of each before providing recommended values for each topic related to Eth2 in the following section. 

### Topics Parameters

| Parameter | Description |
| -------- | -------- |
| `topic_weight` | The weight that is applied to the total score of the specific topic | 
| `time_in_mesh_weight` | This is the weight applied to a positive score that we give to peers for the time they have been in our mesh for this topic. The longer they stay in the mesh the greater their score |
| `time_in_mesh_quantum` | The interval time period that a peer is in the mesh gets additional scoring |
| `time_in_mesh_cap` |  The maximum score we give to peers for staying in the mesh for this topic |
| `first_message_deliveries_weight` | These are the number of unique messages a peer delivers in a topic. This is a positive score and this provides the weight to that score |
| `first_message_deliveries_decay` | The decay rate for the score |
| `first_message_deliveries_cap` | The Cap for the score |
| `mesh_message_deliveries_weight` | This is the number of messages delivered in the mesh within `mesh_messsage_deliveries_window`. Peers must send at least the threshold number of messages for a topic or be penalized. This is the score's weight |
| `mesh_message_deliveries_decay` | This is the decay for the score |
| `mesh_message_deliveries_threshold` | The minimum number of messages a peer must send on the topic |
| `mesh_message_deliveries_cap` | The upper bound of messages that are counted (including decay) before the score is set to 0  |
| `mesh_message_deliveries_activation` | The time a peer is in the mesh before this penalty score is applied |
| `mesh_message_deliveries_window` | The time from first seeing a message that we consider future messages as valid |
| `mesh_failure_penalty_weight` | If a peer gets pruned with a negative mesh message deliveries score we keep track and weight the peer by this value |
| `mesh_failure_penalty_decay` | The decay of this score |
| `invalid_message_deliveries_weight` | The weighting for invalid messages (application rejects or encoding errors) |
| `invalid_message_deliveries_decay` | The decay of this score |

### Topic Score Parameters

#### Beacon Block Topic

| Parameter | Value |  Comment |
| -------- | --- | -------- |
| `topic_weight` | 0.5 | Relative to other topics | 
| `time_in_mesh_weight` | 0.0324 | Weighted small to prevent large scores | 
| `time_in_mesh_quantum` | 1 slot | Count every slot |
| `time_in_mesh_cap` | 300 |  |
| `first_message_deliveries_weight` | 1 | |
| `first_message_deliveries_decay` | 0.9928 | 20 epoch decay to 0 |
| `first_message_deliveries_cap` | 23 | Expected value given average blocks per slot (1) |
| `mesh_message_deliveries_weight` | -0.020408 | Match to worst case (no messages delivered) |
| `mesh_message_deliveries_decay` | 0.9928 | 20 epoch decay to 0 |
| `mesh_message_deliveries_threshold` | 35 | Assume 0.5 blocks per slot and half of them are sent in time |
| `mesh_message_deliveries_cap` | 139 | Natural upper bound for 1 block per slot |
| `mesh_message_deliveries_activation` | 8 epochs | The time required to build up to the threshold assuming average of 0.6 blocks per slot |
| `mesh_message_deliveries_window` | 400ms | Short enough to prevent replay but long enough to account for network delay  |
| `mesh_failure_penalty_weight` |  -0.02048 | Same as `mesh_message_deliveries` |
| `mesh_failure_penalty_decay` | 0.9928 | 20 epoch decay to 0 |
| `invalid_message_deliveries_weight` | -99 |  |
| `invalid_message_deliveries_decay` | 0.9994 | Very slow to decay to remember bad peers |

#### Attestation Aggregate Topic

| Parameter | Value |  Comment |
| -------- | --- | -------- |
| `topic_weight` | 0.5 |  Relative to other topics | 
| `time_in_mesh_weight` | 0.0324 | Weighted small to prevent large scores | 
| `time_in_mesh_quantum` | 1 slot |  Count every slot |
| `time_in_mesh_cap` | 300 |  |
| `first_message_deliveries_weight` | 0.05 | There are lots of messages so each are weighted less |
| `first_message_deliveries_decay` | 0.631 | 10 slot decay to 0 |
| `first_message_deliveries_cap` | `V`/755.712 | Expected_per_slot = v/8/32. Value is expected_per_slot/6/( 1 - decay_rate) the division by 8 is our degree |
| `mesh_message_deliveries_weight` | -0.0026 |  |
| `mesh_message_deliveries_decay` | 0.631 | 10 slot decay to 0 |
| `mesh_message_deliveries_threshold` | `V`/377.856 | aggregators_per_slot = v/8/32. Assume 1/4 get delivered within the window. Value = aggregators_per_slot/4/(1-decay_rate) |
| `mesh_message_deliveries_cap` | `V`/94.464 | Natural bound for expected aggregators per slot. Value = aggregators_per_slot/(1-decay_rate) |
| `mesh_message_deliveries_activation` | 4 slots | The time required to build up to the threshold assuming average of 0.6 messages get delivered per slot |
| `mesh_message_deliveries_window` | 400ms | Short enough to prevent replay but long enough to account for network delay  |
| `mesh_failure_penalty_weight` |  -0.0026 | Same as `mesh_message_deliveries` |
| `mesh_failure_penalty_decay` | 0.631 | 20 epoch decay to 0 |
| `invalid_message_deliveries_weight` | -99 |  |
| `invalid_message_deliveries_decay` | 0.9994 | Very slow to decay to remember bad peers |

NOTE: The `V` represented in the parameters represents the current active validator
count.

#### Subnet and Sync Committee Topics

The recommendations for the subnets are TBD. Current recommendations are to
count invalids.

| Parameter | Value |  Description |
| -------- | --- | -------- |
| `topic_weight` | 0.5 |  Relative to other topics | 
| `time_in_mesh_weight` | 0 |  | 
| `time_in_mesh_quantum` | - |  |
| `time_in_mesh_cap` | - |  |
| `first_message_deliveries_weight` | 0 |  |
| `first_message_deliveries_decay` | - | |
| `first_message_deliveries_cap` | - |   |
| `mesh_message_deliveries_weight` | 0 |  |
| `mesh_message_deliveries_decay` | - |  |
| `mesh_message_deliveries_threshold` | - | |
| `mesh_message_deliveries_cap` | - | |
| `mesh_message_deliveries_activation` |- |  |
| `mesh_message_deliveries_window` | - |  |
| `mesh_failure_penalty_weight` |  0 |  |
| `mesh_failure_penalty_decay` | - |  |
| `invalid_message_deliveries_weight` | -99 |  |
| `invalid_message_deliveries_decay` | 0.9994 | Very slow to decay to remember bad peers |


#### Other topics 

The `voluntary_exit`, `proposer_slashing`, `attester_slashing` topics should
also penalize based on invalid messages. As these topics do not have an
expected number of messages scoring based on mesh_message_deliveries should be
ignored. 
