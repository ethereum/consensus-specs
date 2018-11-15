# Ethereum 2.0 Specifications

[![Join the chat at https://gitter.im/ethereum/sharding](https://badges.gitter.im/ethereum/sharding.svg)](https://gitter.im/ethereum/sharding?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

This repo hosts the current eth2.0 specifications. Discussions about design rationale and proposed changes can be brought up and discussed as issues. Solidified, agreed upon changes to spec can be made through pull requests. 

Core specifications for eth2.0 client validation can be found in [specs/core](specs/core). These are divided into phases. Each subsequent phase depends upon the prior. The current phases specified are:
* [Phase 0 -- The Beacon Chain](specs/core/0_beacon-chain.md)
* [Phase 1 -- Shard Data Chains](specs/core/1_shard-data-chains.md)

## Design goals
The following are the broad design goals for Ethereum 2.0:
* to minimize complexity, even at the cost of some losses in efficiency
* to remain live through major network partitions and when very large portions of nodes going offline
* to select all components such that they are either quantum secure or can be easily swapped out for quantum secure counterparts when available
* to utilize crypto and design techniques that allow for a large participation of validators in total and per unit time
* to allow for a typical consumer laptop with `O(C)` resources to process/validate `O(1)` shards (including any system level validation such as the beacon chain)
