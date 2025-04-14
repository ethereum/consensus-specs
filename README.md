# Ethereum Proof-of-Stake Consensus Specifications

[![Join the chat at https://discord.gg/qGpsxSA](https://img.shields.io/badge/chat-on%20discord-blue.svg)](https://discord.gg/qGpsxSA)

To learn more about proof-of-stake and sharding, see the [PoS documentation](https://ethereum.org/en/developers/docs/consensus-mechanisms/pos/), [sharding documentation](https://ethereum.org/en/upgrades/sharding/) and the [research compendium](https://notes.ethereum.org/s/H1PGqDhpm).

This repository hosts the current Ethereum proof-of-stake specifications. Discussions about design rationale and proposed changes can be brought up and discussed as issues. Solidified, agreed-upon changes to the spec can be made through pull requests.

## Specifications

[![GitHub release](https://img.shields.io/github/v/release/ethereum/consensus-specs)](https://github.com/ethereum/consensus-specs/releases/) [![PyPI version](https://badge.fury.io/py/eth2spec.svg)](https://badge.fury.io/py/eth2spec) [![testgen](https://github.com/ethereum/consensus-specs/actions/workflows/generate_vectors.yml/badge.svg?branch=dev&event=schedule)](https://github.com/ethereum/consensus-specs/actions/workflows/generate_vectors.yml)

Core specifications for Ethereum proof-of-stake clients can be found in [specs](specs). These are divided into features.
Features are researched and developed in parallel, and then consolidated into sequential upgrades when ready.

### Stable Specifications

| Seq. | Code Name | Fork Epoch | Links |
| - | - | - | - |
| 0 | **Phase0** |`0` | [Specs](specs/phase0), [Tests](tests/core/pyspec/eth2spec/test/phase0) |
| 1 | **Altair** | `74240` | [Specs](specs/altair), [Tests](tests/core/pyspec/eth2spec/test/altair) |
| 2 | **Bellatrix** | `144896` | [Specs](specs/bellatrix), [Tests](tests/core/pyspec/eth2spec/test/bellatrix) |
| 3 | **Capella** | `194048` | [Specs](specs/capella), [Tests](tests/core/pyspec/eth2spec/test/capella) |
| 4 | **Deneb** | `269568` | [Specs](specs/deneb), [Tests](tests/core/pyspec/eth2spec/test/deneb) |

### In-development Specifications

| Seq. | Code Name | Fork Epoch | Links |
| - | - | - | - |
| 5 | **Electra** | TBD | [Specs](specs/electra), [Tests](tests/core/pyspec/eth2spec/test/electra) |
| 6 | **Fulu** | TBD | [Specs](specs/fulu), [Tests](tests/core/pyspec/eth2spec/test/fulu) |

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
