# Ethereum 2.0 Specifications

[![Join the chat at https://discord.gg/qGpsxSA](https://img.shields.io/badge/chat-on%20discord-blue.svg)](https://discord.gg/qGpsxSA) [![Join the chat at https://gitter.im/ethereum/sharding](https://badges.gitter.im/ethereum/sharding.svg)](https://gitter.im/ethereum/sharding?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

To learn more about sharding and Ethereum 2.0 (Serenity), see the [sharding FAQ](https://eth.wiki/sharding/Sharding-FAQs) and the [research compendium](https://notes.ethereum.org/s/H1PGqDhpm).

This repository hosts the current Eth2 specifications. Discussions about design rationale and proposed changes can be brought up and discussed as issues. Solidified, agreed-upon changes to the spec can be made through pull requests.


## Specs

[![GitHub release](https://img.shields.io/github/v/release/ethereum/eth2.0-specs)](https://github.com/ethereum/eth2.0-specs/releases/) [![PyPI version](https://badge.fury.io/py/eth2spec.svg)](https://badge.fury.io/py/eth2spec)

Core specifications for Eth2 clients be found in [specs](specs/). These are divided into phases. Each subsequent phase depends upon the prior. The current phases specified are:

### Phase 0

* [The Beacon Chain](specs/phase0/beacon-chain.md)
* [Beacon Chain Fork Choice](specs/phase0/fork-choice.md)
* [Deposit Contract](specs/phase0/deposit-contract.md)
* [Honest Validator](specs/phase0/validator.md)
* [P2P Networking](specs/phase0/p2p-interface.md)

### Light clients

* [Beacon chain changes](specs/lightclient/beacon-chain.md)
* [Light client sync protocol](specs/lightclient/sync-protocol.md)

### Sharding

The sharding spec is still actively in R&D; see the most recent available pull request [here](https://github.com/ethereum/eth2.0-specs/pull/2146) and some technical details [here](https://hackmd.io/@HWeNw8hNRimMm2m2GH56Cw/B1YJPGkpD).

### Merge

The merge is still actively in R&D; see an [ethresear.ch](https://ethresear.ch) post describing the proposed basic mechanism [here](https://ethresear.ch/t/the-eth1-eth2-transition/6265) and the section of [ethereum.org](https://ethereum.org) describing the merge at a high level [here](https://ethereum.org/en/eth2/docking/).

### Accompanying documents can be found in [specs](specs) and include:

* [SimpleSerialize (SSZ) spec](ssz/simple-serialize.md)
* [Merkle proof formats](ssz/merkle-proofs.md)
* [General test format](tests/formats/README.md)

## Additional specifications for client implementers

Additional specifications and standards outside of requisite client functionality can be found in the following repos:

* [Eth2 APIs](https://github.com/ethereum/eth2.0-apis)
* [Eth2 Metrics](https://github.com/ethereum/eth2.0-metrics/)
* [Interop Standards in Eth2 PM](https://github.com/ethereum/eth2.0-pm/tree/master/interop)

## Design goals

The following are the broad design goals for Ethereum 2.0:
* to minimize complexity, even at the cost of some losses in efficiency
* to remain live through major network partitions and when very large portions of nodes go offline
* to select all components such that they are either quantum secure or can be easily swapped out for quantum secure counterparts when available
* to utilize crypto and design techniques that allow for a large participation of validators in total and per unit time
* to allow for a typical consumer laptop with `O(C)` resources to process/validate `O(1)` shards (including any system level validation such as the beacon chain)


## Useful external resources

* [Design Rationale](https://notes.ethereum.org/s/rkhCgQteN#)
* [Phase 0 Onboarding Document](https://notes.ethereum.org/s/Bkn3zpwxB)
* [Combining GHOST and Casper paper](https://arxiv.org/abs/2003.03052)


## For spec contributors

Documentation on the different components used during spec writing can be found here:
* [YAML Test Generators](tests/generators/README.md)
* [Executable Python Spec, with Py-tests](tests/core/pyspec/README.md)
