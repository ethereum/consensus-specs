# Ethereum 2.0 Specifications

[![Join the chat at https://gitter.im/ethereum/sharding](https://badges.gitter.im/ethereum/sharding.svg)](https://gitter.im/ethereum/sharding?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

To learn more about sharding and eth2.0/Serenity, see the [sharding FAQ](https://github.com/ethereum/wiki/wiki/Sharding-FAQs) and the [research compendium](https://notes.ethereum.org/s/H1PGqDhpm).

This repo hosts the current eth2.0 specifications. Discussions about design rationale and proposed changes can be brought up and discussed as issues. Solidified, agreed upon changes to spec can be made through pull requests.

# Specs

Core specifications for eth2.0 client validation can be found in [specs/core](specs/core). These are divided into phases. Each subsequent phase depends upon the prior. The current phases specified are:
* [Phase 0 -- The Beacon Chain](specs/core/0_beacon-chain.md)
* [Phase 1 -- Custody game](specs/core/1_custody-game.md)
* [Phase 1 -- Shard Data Chains](specs/core/1_shard-data-chains.md)

Accompanying documents can be found in [specs](specs) and include
* [SimpleSerialize (SSZ) spec](specs/simple-serialize.md)
* [BLS signature verification](specs/bls_signature.md)
* [General test format](specs/test_formats/README.md)
* [Honest validator implementation doc](specs/validator/0_beacon-chain-validator.md)
* [Merkle proof formats](specs/light_client/merkle_proofs.md)
* [Light client syncing protocol](specs/light_client/sync_protocol.md)

## Design goals
The following are the broad design goals for Ethereum 2.0:
* to minimize complexity, even at the cost of some losses in efficiency
* to remain live through major network partitions and when very large portions of nodes go offline
* to select all components such that they are either quantum secure or can be easily swapped out for quantum secure counterparts when available
* to utilize crypto and design techniques that allow for a large participation of validators in total and per unit time
* to allow for a typical consumer laptop with `O(C)` resources to process/validate `O(1)` shards (including any system level validation such as the beacon chain)
