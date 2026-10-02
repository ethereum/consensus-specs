# Ethereum Consensus Specifications

[![tests](https://github.com/ethereum/consensus-specs/actions/workflows/tests.yml/badge.svg?branch=master&event=schedule)](https://github.com/ethereum/consensus-specs/actions/workflows/tests.yml)
[![image](https://img.shields.io/pypi/v/eth-consensus-specs.svg)](https://pypi.python.org/pypi/eth-consensus-specs)
[![image](https://img.shields.io/pypi/l/eth-consensus-specs.svg)](https://pypi.python.org/pypi/eth-consensus-specs)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?logo=discord&logoColor=white)](https://discord.gg/qGpsxSA)

This repository hosts the Ethereum
[proof-of-stake](https://ethereum.org/en/developers/docs/consensus-mechanisms/pos/)
specifications for consensus-layer clients. Design rationale and proposed
changes are discussed in issues. Agreed-upon changes are made through pull
requests. Specifications can be found in [specs](specs), arranged by upgrade.
Each upgrade builds on the previous, specifying only what it changes. Individual
[features](specs/_features) are developed in parallel and are folded into an
upgrade when ready.

### Stable specifications

| Seq. | Code Name     | Fork Epoch | Link                    |
| ---- | ------------- | ---------- | ----------------------- |
| 0    | **Phase0**    | `0`        | [Spec](specs/phase0)    |
| 1    | **Altair**    | `74240`    | [Spec](specs/altair)    |
| 2    | **Bellatrix** | `144896`   | [Spec](specs/bellatrix) |
| 3    | **Capella**   | `194048`   | [Spec](specs/capella)   |
| 4    | **Deneb**     | `269568`   | [Spec](specs/deneb)     |
| 5    | **Electra**   | `364032`   | [Spec](specs/electra)   |
| 6    | **Fulu**      | `411392`   | [Spec](specs/fulu)      |

### Unstable specifications

| Seq. | Code Name | Fork Epoch | Link                |
| ---- | --------- | ---------- | ------------------- |
| 7    | **Gloas** | TBD        | [Spec](specs/gloas) |
| 8    | **Heze**  | TBD        | [Spec](specs/heze)  |

### Rendered viewers

- https://ethereum.github.io/spec-viewer/
- https://ethereum.github.io/consensus-specs/

### Reference tests

- [Release assets](https://github.com/ethereum/consensus-specs/releases)
- [Nightly artifacts](https://github.com/ethereum/consensus-specs/actions/workflows/tests.yml)

### Design goals

- Minimize complexity, even at the cost of some losses in efficiency.
- Remain live through major network partitions and mass node outages.
- Select components that are quantum-secure or easy to swap out.
- Use crypto and design techniques that support a large validator set.
- Minimize hardware requirements such that a consumer laptop can participate.

### External specifications

- [Beacon APIs](https://github.com/ethereum/beacon-apis)
- [Beacon Metrics](https://github.com/ethereum/beacon-metrics)
- [Builder Specs](https://github.com/ethereum/builder-specs)
- [Cryptography Specs](https://github.com/ethereum/cryptography-specs)
- [Deposit Contract](https://github.com/ethereum/solidity-deposit-contract)
- [Engine APIs](https://github.com/ethereum/execution-apis/tree/main/src/engine)
- [SimpleSerialize Specs](https://github.com/ethereum/ssz-specs)

### Useful resources

- [Design Rationale](https://notes.ethereum.org/s/rkhCgQteN#)
- [Phase0 for Humans](https://notes.ethereum.org/s/Bkn3zpwxB)
- [Combining GHOST and Casper](https://arxiv.org/abs/2003.03052)
- [Vitalik's annotated spec](https://github.com/ethereum/annotated-spec)
- [Upgrading Ethereum](https://eth2book.info)
