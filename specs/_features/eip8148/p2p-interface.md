# EIP-8148 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in EIP-8148](#modifications-in-eip-8148)
  - [Helpers](#helpers)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-8148.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Modifications in EIP-8148

### Helpers

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIP8148_FORK_EPOCH:
        return EIP8148_FORK_VERSION
    if epoch >= GLOAS_FORK_EPOCH:
        return GLOAS_FORK_VERSION
    if epoch >= FULU_FORK_EPOCH:
        return FULU_FORK_VERSION
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
