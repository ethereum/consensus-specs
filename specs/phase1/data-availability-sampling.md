# Ethereum 2.0 Phase 1 -- Data Availability Sampling

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `SampleIndex` | `uint64` | A sample index, corresponding to chunk of extended data |
| `BLSPoint` | `uint256` | A number `x` in the range `0 <= x < MODULUS` |


## New containers

### DASSample

```python
class DASSample(Container):
    slot: Slot
    shard: Shard
    index: SampleIndex
    proof: BLSKateProof
    data: Vector[BLSPoint, POINTS_PER_SAMPLE]
```

## Helper functions

```python
def recover_data(data: Sequence[Optional[Point]]) -> Sequence[Point]:
    ...
```

## DAS functions

```python
def extend_data(data: Sequence[Point]) -> Sequence[Point]:
    ...
```

```python
def unextend_data(extended_data: Sequence[Point]) -> Sequence[Point]:
    ...
```

```python
def sample_data(extended_data: Sequence[Point]) -> Sequence[DASSample]:
    ...
```

```python
def verify_sample(sample: DASSample):
    ...
```

```python
def reconstruct_extended_data(samples: Sequence[DASSample]) -> Sequence[Point]:
    ...
```
