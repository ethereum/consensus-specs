# Ethereum Proof-of-Stake Consensus Specifications

[![Join the chat at https://discord.gg/qGpsxSA](https://img.shields.io/badge/chat-on%20discord-blue.svg)](https://discord.gg/qGpsxSA)
[![testgen](https://github.com/ethereum/consensus-specs/actions/workflows/generate_vectors.yml/badge.svg?branch=dev&event=schedule)](https://github.com/ethereum/consensus-specs/actions/workflows/generate_vectors.yml)

This repository hosts the current Ethereum
[proof-of-stake](https://ethereum.org/en/developers/docs/consensus-mechanisms/pos/) specifications.
Discussions about design rationale and proposed changes can be brought up and discussed as issues.
Solidified, agreed-upon changes to the specifications can be made through pull requests.

## Specifications

Core specifications for Ethereum proof-of-stake clients can be found in [specs](specs). These are
divided into features. Features are researched and developed in parallel, and then consolidated into
sequential upgrades when ready.

### Stable Specifications

| Seq. | Code Name     | Fork Epoch | Links                                                                        |
| ---- | ------------- | ---------- | ---------------------------------------------------------------------------- |
| 0    | **Phase0**    | `0`        | [Specs](specs/phase0), [Tests](tests/core/pyspec/eth2spec/test/phase0)       |
| 1    | **Altair**    | `74240`    | [Specs](specs/altair), [Tests](tests/core/pyspec/eth2spec/test/altair)       |
| 2    | **Bellatrix** | `144896`   | [Specs](specs/bellatrix), [Tests](tests/core/pyspec/eth2spec/test/bellatrix) |
| 3    | **Capella**   | `194048`   | [Specs](specs/capella), [Tests](tests/core/pyspec/eth2spec/test/capella)     |
| 4    | **Deneb**     | `269568`   | [Specs](specs/deneb), [Tests](tests/core/pyspec/eth2spec/test/deneb)         |

### In-development Specifications

| Seq. | Code Name   | Fork Epoch | Links                                                                    |
| ---- | ----------- | ---------- | ------------------------------------------------------------------------ |
| 5    | **Electra** | TBD        | [Specs](specs/electra), [Tests](tests/core/pyspec/eth2spec/test/electra) |
| 6    | **Fulu**    | TBD        | [Specs](specs/fulu), [Tests](tests/core/pyspec/eth2spec/test/fulu)       |

### Accompanying documents

- [SimpleSerialize (SSZ) spec](ssz/simple-serialize.md)
- [Merkle proof formats](ssz/merkle-proofs.md)
- [General test format](tests/formats/README.md)

### External specifications

Additional specifications and standards outside of requisite client functionality can be found in
the following repositories:

- [Beacon APIs](https://github.com/ethereum/beacon-apis)
- [Engine APIs](https://github.com/ethereum/execution-apis/tree/main/src/engine)
- [Beacon Metrics](https://github.com/ethereum/beacon-metrics)
- [Builder Specs](https://github.com/ethereum/builder-specs)

### Reference tests

Reference tests built from the executable Python spec are available in the [Ethereum Proof-of-Stake
Consensus Spec Tests](https://github.com/ethereum/consensus-spec-tests) repository. Compressed
tarballs are available for each release
[here](https://github.com/ethereum/consensus-spec-tests/releases). Nightly reference tests are
available
[here](https://github.com/ethereum/consensus-specs/actions/workflows/generate_vectors.yml).

## Contributors

### Installation and usage

Clone the repository with:

```bash
git clone https://github.com/ethereum/consensus-specs.git
```

Switch to the directory:

```bash
cd consensus-specs
```

View the help output:

```bash
make help
```

### Design goals

The following are the broad design goals for the Ethereum proof-of-stake consensus specifications:

- Minimize complexity, even at the cost of some losses in efficiency.
- Remain live through major network partitions and when very large portions of nodes go offline.
- Select components that are quantum secure or easily swappable for quantum-secure alternatives.
- Utilize crypto and design techniques that allow for a large participation of validators.
- Minimize hardware requirements such that a consumer laptop can participate.

### Useful resources

- [Design Rationale](https://notes.ethereum.org/s/rkhCgQteN#)
- [Phase0 Onboarding Document](https://notes.ethereum.org/s/Bkn3zpwxB)
- [Combining GHOST and Casper paper](https://arxiv.org/abs/2003.03052)
- [Online specifications viewer](https://ethereum.github.io/consensus-specs/)
- [The Eth2 Book](https://eth2book.info)
- [PySpec Tests](tests/core/pyspec/README.md)
- [Reference Tests Generators](tests/generators/README.md)
