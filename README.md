# Ethereum Proof-of-Stake Consensus Specifications

[![Join the chat at https://discord.gg/qGpsxSA](https://img.shields.io/badge/chat-on%20discord-blue.svg)](https://discord.gg/qGpsxSA) [![Join the chat at https://gitter.im/ethereum/sharding](https://badges.gitter.im/ethereum/sharding.svg)](https://gitter.im/ethereum/sharding?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

To learn more about proof-of-stake and sharding, see the [PoS FAQ](https://eth.wiki/en/concepts/proof-of-stake-faqs), [sharding FAQ](https://eth.wiki/sharding/Sharding-FAQs) and the [research compendium](https://notes.ethereum.org/s/H1PGqDhpm).

This repository hosts the current Ethereum proof-of-stake specifications. Discussions about design rationale and proposed changes can be brought up and discussed as issues. Solidified, agreed-upon changes to the spec can be made through pull requests.

## Specs

[![GitHub release](https://img.shields.io/github/v/release/ethereum/eth2.0-specs)](https://github.com/ethereum/eth2.0-specs/releases/) [![PyPI version](https://badge.fury.io/py/eth2spec.svg)](https://badge.fury.io/py/eth2spec)

Core specifications for Ethereum proof-of-stake clients can be found in [specs](specs/). These are divided into features.
Features are researched and developed in parallel, and then consolidated into sequential upgrades when ready.

### Stable Specifications

| Seq. | Code Name | Fork Epoch | Specs |
| - | - | - | - |
| 0 | **Phase0** |`0` | <ul><li>Core</li><ul><li>[The beacon chain](specs/phase0/beacon-chain.md)</li><li>[Deposit contract](specs/phase0/deposit-contract.md)</li><li>[Beacon chain fork choice](specs/phase0/fork-choice.md)</li></ul><li>Additions</li><ul><li>[Honest validator guide](specs/phase0/validator.md)</li><li>[P2P networking](specs/phase0/p2p-interface.md)</li><li>[Weak subjectivity](specs/phase0/weak-subjectivity.md)</li></ul></ul> |
| 1 |  **Altair** | `74240` | <ul><li>Core</li><ul><li>[Beacon chain changes](specs/altair/beacon-chain.md)</li><li>[Altair fork](specs/altair/fork.md)</li></ul><li>Additions</li><ul><li>[Light client sync protocol](specs/altair/light-client/sync-protocol.md) ([full node](specs/altair/light-client/full-node.md), [light client](specs/altair/light-client/light-client.md), [networking](specs/altair/light-client/p2p-interface.md))</li><li>[Honest validator guide changes](specs/altair/validator.md)</li><li>[P2P networking](specs/altair/p2p-interface.md)</li></ul></ul> |
| 2 | **Bellatrix** <br/> (["The Merge"](https://ethereum.org/en/upgrades/merge/)) | `144896` | <ul><li>Core</li><ul><li>[Beacon Chain changes](specs/bellatrix/beacon-chain.md)</li><li>[Bellatrix fork](specs/bellatrix/fork.md)</li><li>[Fork choice changes](specs/bellatrix/fork-choice.md)</li></ul><li>Additions</li><ul><li>[Honest validator guide changes](specs/bellatrix/validator.md)</li><li>[P2P networking](specs/bellatrix/p2p-interface.md)</li></ul></ul> |

### In-development Specifications
| Code Name or Topic | Specs | Notes |
| - | - | - |
| Capella (tentative) | <ul><li>Core</li><ul><li>[Beacon chain changes](specs/capella/beacon-chain.md)</li><li>[Capella fork](specs/capella/fork.md)</li></ul><li>Additions</li><ul><li>[Validator additions](specs/capella/validator.md)</li></ul></ul> |
| EIP4844 (tentative) | <ul><li>Core</li><ul><li>[Beacon Chain changes](specs/eip4844/beacon-chain.md)</li><li>[EIP-4844 fork](specs/eip4844/fork.md)</li><li>[Polynomial commitments](specs/eip4844/polynomial-commitments.md)</li></ul><li>Additions</li><ul><li>[Honest validator guide changes](specs/eip4844/validator.md)</li><li>[P2P networking](specs/eip4844/p2p-interface.md)</li></ul></ul> |
| Sharding (outdated) | <ul><li>Core</li><ul><li>[Beacon Chain changes](specs/sharding/beacon-chain.md)</li></ul><li>Additions</li><ul><li>[P2P networking](specs/sharding/p2p-interface.md)</li></ul></ul> |
| Custody Game (outdated) | <ul><li>Core</li><ul><li>[Beacon Chain changes](specs/custody_game/beacon-chain.md)</li></ul><li>Additions</li><ul><li>[Honest validator guide changes](specs/custody_game/validator.md)</li></ul></ul> | Dependent on sharding |
| Data Availability Sampling (outdated) | <ul><li>Core</li><ul><li>[Core types and functions](specs/das/das-core.md)</li><li>[Fork choice changes](specs/das/fork-choice.md)</li></ul><li>Additions</li><ul><li>[P2P Networking](specs/das/p2p-interface.md)</li><li>[Sampling process](specs/das/sampling.md)</li></ul></ul> | <ul><li> Dependent on sharding</li><li>[Technical explainer](https://hackmd.io/@HWeNw8hNRimMm2m2GH56Cw/B1YJPGkpD)</li></ul> |

### Accompanying documents can be found in [specs](specs) and include:

* [SimpleSerialize (SSZ) spec](ssz/simple-serialize.md)
* [Merkle proof formats](ssz/merkle-proofs.md)
* [General test format](tests/formats/README.md)

## Additional specifications for client implementers

Additional specifications and standards outside of requisite client functionality can be found in the following repos:

* [Beacon APIs](https://github.com/ethereum/beacon-apis)
* [Beacon Metrics](https://github.com/ethereum/beacon-metrics/)

## Design goals

The following are the broad design goals for the Ethereum proof-of-stake consensus specifications:
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

## Consensus spec tests

Conformance tests built from the executable python spec are available in the [Ethereum Proof-of-Stake Consensus Spec Tests](https://github.com/ethereum/consensus-spec-tests) repo. Compressed tarballs are available in [releases](https://github.com/ethereum/consensus-spec-tests/releases).
