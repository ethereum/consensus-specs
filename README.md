# Ethereum Proof-of-Stake Consensus Specifications

[![Join the chat at https://discord.gg/qGpsxSA](https://img.shields.io/badge/chat-on%20discord-blue.svg)](https://discord.gg/qGpsxSA)

To learn more about proof-of-stake and sharding, see the [PoS documentation](https://ethereum.org/en/developers/docs/consensus-mechanisms/pos/), [sharding documentation](https://ethereum.org/en/upgrades/sharding/) and the [research compendium](https://notes.ethereum.org/s/H1PGqDhpm).

This repository hosts the current Ethereum proof-of-stake specifications. Discussions about design rationale and proposed changes can be brought up and discussed as issues. Solidified, agreed-upon changes to the spec can be made through pull requests.

## Specifications

[![GitHub release](https://img.shields.io/github/v/release/ethereum/consensus-specs)](https://github.com/ethereum/consensus-specs/releases/) [![PyPI version](https://badge.fury.io/py/eth2spec.svg)](https://badge.fury.io/py/eth2spec) [![testgen](https://github.com/ethereum/consensus-specs/actions/workflows/generate_vectors.yml/badge.svg?branch=dev&event=schedule)](https://github.com/ethereum/consensus-specs/actions/workflows/generate_vectors.yml)

Core specifications for Ethereum proof-of-stake clients can be found in [specs](specs). These are divided into features.
Features are researched and developed in parallel, and then consolidated into sequential upgrades when ready.

### Stable Specifications

| Seq. | Code Name | Fork Epoch | Specs |
| - | - | - | - |
| 0 | **Phase0** |`0` | <ul><li>Core</li><ul><li>[The beacon chain](specs/phase0/beacon-chain.md)</li><li>[Deposit contract](specs/phase0/deposit-contract.md)</li><li>[Beacon chain fork choice](specs/phase0/fork-choice.md)</li></ul><li>Additions</li><ul><li>[Honest validator guide](specs/phase0/validator.md)</li><li>[P2P networking](specs/phase0/p2p-interface.md)</li><li>[Weak subjectivity](specs/phase0/weak-subjectivity.md)</li></ul></ul> |
| 1 | **Altair** | `74240` | <ul><li>Core</li><ul><li>[Beacon chain changes](specs/altair/beacon-chain.md)</li><li>[Altair fork](specs/altair/fork.md)</li></ul><li>Additions</li><ul><li>[Light client sync protocol](specs/altair/light-client/sync-protocol.md) ([full node](specs/altair/light-client/full-node.md), [light client](specs/altair/light-client/light-client.md), [networking](specs/altair/light-client/p2p-interface.md))</li><li>[Honest validator guide changes](specs/altair/validator.md)</li><li>[P2P networking](specs/altair/p2p-interface.md)</li></ul></ul> |
| 2 | **Bellatrix** <br/> (["The Merge"](https://ethereum.org/en/upgrades/merge/)) | `144896` | <ul><li>Core</li><ul><li>[Beacon Chain changes](specs/bellatrix/beacon-chain.md)</li><li>[Bellatrix fork](specs/bellatrix/fork.md)</li><li>[Fork choice changes](specs/bellatrix/fork-choice.md)</li></ul><li>Additions</li><ul><li>[Honest validator guide changes](specs/bellatrix/validator.md)</li><li>[P2P networking](specs/bellatrix/p2p-interface.md)</li></ul></ul> |
| 3 | **Capella** | `194048` | <ul><li>Core</li><ul><li>[Beacon chain changes](specs/capella/beacon-chain.md)</li><li>[Capella fork](specs/capella/fork.md)</li></ul><li>Additions</li><ul><li>[Light client sync protocol changes](specs/capella/light-client/sync-protocol.md) ([fork](specs/capella/light-client/fork.md), [full node](specs/capella/light-client/full-node.md), [networking](specs/capella/light-client/p2p-interface.md))</li><li>[Validator additions](specs/capella/validator.md)</li><li>[P2P networking](specs/capella/p2p-interface.md)</li></ul></ul> |
| 4 | **Deneb** | `269568` | <ul><li>Core</li><ul><li>[Beacon Chain changes](specs/deneb/beacon-chain.md)</li><li>[Deneb fork](specs/deneb/fork.md)</li><li>[Polynomial commitments](specs/deneb/polynomial-commitments.md)</li><li>[Fork choice changes](specs/deneb/fork-choice.md)</li></ul><li>Additions</li><ul><li>[Light client sync protocol changes](specs/deneb/light-client/sync-protocol.md) ([fork](specs/deneb/light-client/fork.md), [full node](specs/deneb/light-client/full-node.md), [networking](specs/deneb/light-client/p2p-interface.md))</li><li>[Honest validator guide changes](specs/deneb/validator.md)</li><li>[P2P networking](specs/deneb/p2p-interface.md)</li></ul></ul> |

### In-development Specifications

| Seq. | Code Name | Fork Epoch | Specs |
| - | - | - | - |
| 5 | **Electra** | TBD | <ul><li>Core</li><ul><li>[Beacon Chain changes](specs/electra/beacon-chain.md)</li><li>[Electra fork](specs/electra/fork.md)</li></ul><li>Additions</li><ul><li>[Light client sync protocol changes](specs/electra/light-client/sync-protocol.md) ([fork](specs/electra/light-client/fork.md), [networking](specs/electra/light-client/p2p-interface.md))</li><li>[Honest validator guide changes](specs/electra/validator.md)</li><li>[P2P networking](specs/electra/p2p-interface.md)</li></ul></ul> |
| 6 | **Fulu** | TBD | <ul><li>Core</li><ul><li>[Beacon Chain changes](specs/fulu/beacon-chain.md)</li><li>[Fulu fork](specs/fulu/fork.md)</li><li>[Data availability sampling core](specs/fulu/das-core.md)</li><li>[Polynomial commitments sampling](specs/fulu/polynomial-commitments-sampling.md)</li><li>[Fork choice changes](specs/fulu/fork-choice.md)</li></ul><li>Additions</li><ul><li>[Honest validator guide changes](specs/fulu/validator.md)</li><li>[P2P networking](specs/fulu/p2p-interface.md)</li><li>[Peer sampling](specs/fulu/peer-sampling.md)</li></ul></ul> |

### Accompanying documents can be found in [specs](specs) and include:

* [SimpleSerialize (SSZ) spec](ssz/simple-serialize.md)
* [Merkle proof formats](ssz/merkle-proofs.md)
* [General test format](tests/formats/README.md)

## Additional specifications for client implementers

Additional specifications and standards outside of requisite client functionality can be found in the following repos:

* [Beacon APIs](https://github.com/ethereum/beacon-apis)
* [Engine APIs](https://github.com/ethereum/execution-apis/tree/main/src/engine)
* [Beacon Metrics](https://github.com/ethereum/beacon-metrics)

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

## Online viewer of the latest release (latest `master` branch)

[Ethereum Consensus Specs](https://ethereum.github.io/consensus-specs/)

## Consensus spec tests

Conformance tests built from the executable python spec are available in the [Ethereum Proof-of-Stake Consensus Spec Tests](https://github.com/ethereum/consensus-spec-tests) repo. Compressed tarballs are available in [releases](https://github.com/ethereum/consensus-spec-tests/releases).

## Installation and usage

Clone the repository with:

```bash
git clone https://github.com/ethereum/consensus-specs.git
```

Switch to the directory:

```bash
cd consensus-specs
```

Run the tests:

```bash
make test
```
