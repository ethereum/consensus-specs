# EIP-7549 -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Containers](#containers)
  - [Extended containers](#extended-containers)
    - [AttestationData](#attestationdata)
    - [Attestation](#attestation)
- [Helper functions](#helper-functions)
  - [Beacon state accessors](#beacon-state-accessors)
    - [Modified `get_attestation_index`](#modified-get_attestation_index)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the beacon chain specification to move the attestation committee index outside of the signed message. For motivation, refer to [EIP-7549](https://eips.ethereum.org/EIPS/eip-7549).

*Note:* This specification is built upon [Deneb](../../deneb/beacon_chain.md) and is under active development.

## Containers

### Extended containers

#### AttestationData

```python
class AttestationData(Container):
    slot: Slot
    # index: CommitteeIndex  # [Modified in EIP7549]
    # LMD GHOST vote
    beacon_block_root: Root
    # FFG vote
    source: Checkpoint
    target: Checkpoint
```

#### Attestation

```python
class Attestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    index: CommitteeIndex  # [New in EIP7549]
    signature: BLSSignature
```

## Helper functions

### Beacon state accessors

#### Modified `get_attestation_index`

```python
def get_attestation_index(attestation: Attestation) -> CommitteeIndex:
    return attestation.index
```

