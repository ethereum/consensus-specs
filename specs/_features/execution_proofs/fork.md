# Execution Proofs -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
- [Fork to Execution Proofs](#fork-to-execution-proofs)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the Execution Proofs upgrade, enabling stateless validation of execution payloads through cryptographic proofs.

## Configuration

Warning: this configuration is not definitive.

| Name                              | Value                                 |
| --------------------------------- | ------------------------------------- |
| `EXECUTION_PROOFS_FORK_VERSION`   | `Version('0x0A000000')`               |
| `EXECUTION_PROOFS_FORK_EPOCH`     | `Epoch(18446744073709551615)` **TBD** |

## Helper functions

### Misc

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EXECUTION_PROOFS_FORK_EPOCH:
        return EXECUTION_PROOFS_FORK_VERSION
    if epoch >= FULU_FORK_EPOCH:
        return FULU_FORK_VERSION
    if epoch >= EIP7732_FORK_EPOCH:
        return EIP7732_FORK_VERSION
    if epoch >= ELECTRA_FORK_EPOCH:
        return ELECTRA_FORK_VERSION
    if epoch >= DENEB_FORK_EPOCH:
        return DENEB_FORK_VERSION
    if epoch >= CAPELLA_FORK_EPOCH:
        return CAPELLA_FORK_VERSION
    if epoch >= BELLATRIX_FORK_EPOCH:
        return BELLATRIX_FORK_VERSION
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

## Fork to Execution Proofs

### Fork trigger

The fork is triggered at epoch `EXECUTION_PROOFS_FORK_EPOCH`.

### Upgrading the state

Since execution proofs are handled externally (similar to blob data), no changes to the `BeaconState` format are required. The upgrade only updates the fork version.

```python
def upgrade_to_execution_proofs(pre: fulu.BeaconState) -> BeaconState:
    return pre.copy(
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=EXECUTION_PROOFS_FORK_VERSION,
            epoch=EXECUTION_PROOFS_FORK_EPOCH,
        )
    )
```