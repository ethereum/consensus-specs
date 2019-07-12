# Ethereum 2.0 Specifications

[![Join the chat at https://gitter.im/ethereum/sharding](https://badges.gitter.im/ethereum/sharding.svg)](https://gitter.im/ethereum/sharding?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

To learn more about sharding and Ethereum 2.0 (Serenity), see the [sharding FAQ](https://github.com/ethereum/wiki/wiki/Sharding-FAQ) and the [research compendium](https://notes.ethereum.org/s/H1PGqDhpm).

This repository hosts the current Eth 2.0 specifications. Discussions about design rationale and proposed changes can be brought up and discussed as issues. Solidified, agreed-upon changes to the spec can be made through pull requests.


## Specs

Core specifications for Eth 2.0 client validation can be found in [specs/core](specs/core). These are divided into phases. Each subsequent phase depends upon the prior. The current phases specified are:

### Phase 0
* [The Beacon Chain](specs/core/0_beacon-chain.md)
* [Fork Choice](specs/core/0_fork-choice.md)
* [Deposit Contract](specs/core/0_deposit-contract.md)
* [Honest Validator](specs/validator/0_beacon-chain-validator.md)

### Phase 1
* [Custody Game](specs/core/1_custody-game.md)
* [Shard Data Chains](specs/core/1_shard-data-chains.md)

### Phase 2

Phase 2 is still actively in R&D and does not yet have any formal specifications.

See the [Eth 2.0 Phase 2 Wiki](https://hackmd.io/UzysWse1Th240HELswKqVA?view) for current progress, discussions, and definitions regarding this work.

### Accompanying documents can be found in [specs](specs) and include:

* [SimpleSerialize (SSZ) spec](specs/simple-serialize.md)
* [BLS signature verification](specs/bls_signature.md)
* [General test format](specs/test_formats/README.md)
* [Merkle proof formats](specs/light_client/merkle_proofs.md)
* [Light client syncing protocol](specs/light_client/sync_protocol.md)
* [Beacon node API for validator](specs/validator/0_beacon-node-validator-api.md)


## Design goals

The following are the broad design goals for Ethereum 2.0:
* to minimize complexity, even at the cost of some losses in efficiency
* to remain live through major network partitions and when very large portions of nodes go offline
* to select all components such that they are either quantum secure or can be easily swapped out for quantum secure counterparts when available
* to utilize crypto and design techniques that allow for a large participation of validators in total and per unit time
* to allow for a typical consumer laptop with `O(C)` resources to process/validate `O(1)` shards (including any system level validation such as the beacon chain)


## For spec contributors

Documentation on the different components used during spec writing can be found here:
* [YAML Test Generators](test_generators/README.md)
* [Executable Python Spec, with Py-tests](test_libs/pyspec/README.md)

