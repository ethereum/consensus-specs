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

### Data extension

Implementations:
- [Python](https://github.com/protolambda/partial_fft/blob/master/das_fft.py)
- [Go](https://github.com/protolambda/go-kate/blob/master/das_extension.go)

```python
def das_fft_extension(data: Sequence[Point]) -> Sequence[Point]:
    """Given some even-index values of an IFFT input, compute the odd-index inputs, such that the second output half is all zeroes."""
    poly = inverse_fft(data)
    return fft(poly + [0]*len(poly))[1::2]
```

### Data recovery

See [Reed-Solomon erasure code recovery in n*log^2(n) time with FFTs](https://ethresear.ch/t/reed-solomon-erasure-code-recovery-in-n-log-2-n-time-with-ffts/3039) for theory.
Implementations:
- [Original Python](https://github.com/ethereum/research/blob/master/mimc_stark/recovery.py)
- [New optimized approach in python](https://github.com/ethereum/research/tree/master/polynomial_reconstruction)
- [Old approach in Go](https://github.com/protolambda/go-kate/blob/master/recovery.go)

```python
def recover_data(data: Sequence[Optional[Point]]) -> Sequence[Point]:
    """Given an a subset of half or more of the values (missing values are None), recover the None values."""
    ...
```

## DAS functions

```python
def extend_data(data: Sequence[Point]) -> Sequence[Point]:
    # To force adjacent data into the same proofs, reverse-bit-order the whole list.
    evens = [data[reverse_bit_order(i, len(data))] for i in range(len(data))]
    # last step of reverse-bit-order: mix in the extended data.
    # When undoing the reverse bit order: 1st half matches original data, and 2nd half matches the extension.
    odds = das_fft_extension(data)
    return [evens[i//2] if i % 2 == 0 else odds[i//2] for i in range(len(data)*2)]
```

```python
def unextend_data(extended_data: Sequence[Point]) -> Sequence[Point]:
    return [extended_data[reverse_bit_order(i, len(extended_data))] for i in range(len(extended_data)//2)]
```

```python
def check_multi_kate_proof(commitment: BLSCommitment, proof: BLSKateProof, x: Point, ys: Sequence[Point]) -> bool:
    ...
```

```python
def construct_proofs(extended_data_as_poly: Sequence[Point]) -> Sequence[BLSKateProof]:
    """Constructs proofs for samples of extended data (in polynomial form, 2nd half being zeroes)"""
    ... # TODO Use FK20 multi-proof code to construct proofs for a chunk length of POINTS_PER_SAMPLE.
```

```python
def sample_data(slot: Slot, shard: Shard, extended_data: Sequence[Point]) -> Sequence[DASSample]:
    # TODO: padding of last sample (if not a multiple of POINTS_PER_SAMPLE)
    sample_count = len(extended_data) // POINTS_PER_SAMPLE
    assert sample_count <= MAX_SAMPLES_PER_BLOCK
    proofs = construct_proofs(ifft(extended_data))
    return [
        DASSample(
            slot=slot,
            shard=shard,
            index=i,
            proof=proofs[reverse_bit_order(i, sample_count)],  # TODO: proof order depends on API of construct_proofs
            data=reverse_bit_order_list(extended_data[i*POINTS_PER_SAMPLE:(i+1)*POINTS_PER_SAMPLE])  # TODO: can reorder here, or defer
        ) for i in range(sample_count)
    ]
```

```python
def verify_sample(sample: DASSample, sample_count: uint64, commitment: BLSCommitment):
    domain_pos = reverse_bit_order(sample.index, sample_count)
    sample_root_of_unity = ROOT_OF_UNITY**MAX_SAMPLES_PER_BLOCK  # change point-level to sample-level domain
    x = sample_root_of_unity**domain_pos
    assert check_multi_kate_proof(commitment, sample.proof, x, sample.data)
```

```python
def reconstruct_extended_data(samples: Sequence[Optional[DASSample]]) -> Sequence[Point]:
    extended_data = [None] * (len(samples) * POINTS_PER_SAMPLE)
    for sample in samples:
        offset = sample.index * POINTS_PER_SAMPLE
        for i, p in enumerate(sample.data):
            extended_data[offset+i] = p
    return recover_data(extended_data)
```
