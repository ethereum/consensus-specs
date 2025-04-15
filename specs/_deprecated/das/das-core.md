# Data Availability Sampling -- Core

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Custom types](#custom-types)
- [Configuration](#configuration)
  - [Misc](#misc)
- [New containers](#new-containers)
  - [`DASSample`](#dassample)
- [Helper functions](#helper-functions)
  - [Reverse bit ordering](#reverse-bit-ordering)
    - [`reverse_bit_order`](#reverse_bit_order)
    - [`reverse_bit_order_list`](#reverse_bit_order_list)
  - [Data extension](#data-extension)
  - [Data recovery](#data-recovery)
- [DAS functions](#das-functions)

<!-- mdformat-toc end -->

## Custom types

We define the following Python custom types for type hinting and readability:

| Name          | SSZ equivalent | Description                                             |
| ------------- | -------------- | ------------------------------------------------------- |
| `SampleIndex` | `uint64`       | A sample index, corresponding to chunk of extended data |

## Configuration

### Misc

| Name                | Value           | Notes                                                             |
| ------------------- | --------------- | ----------------------------------------------------------------- |
| `MAX_RESAMPLE_TIME` | `TODO` (= TODO) | Time window to sample a shard blob and put it on vertical subnets |

## New containers

### `DASSample`

```python
class DASSample(Container):
    slot: Slot
    shard: Shard
    index: SampleIndex
    proof: BLSCommitment
    data: Vector[BLSPoint, POINTS_PER_SAMPLE]
```

## Helper functions

### Reverse bit ordering

#### `reverse_bit_order`

```python
def reverse_bit_order(n: int, order: int):
    """
    Reverse the bit order of an integer n
    """
    assert is_power_of_two(order)
    return int(('{:0' + str(order.bit_length() - 1) + 'b}').format(n)[::-1], 2)
```

#### `reverse_bit_order_list`

```python
def reverse_bit_order_list(elements: Sequence[int]) -> Sequence[int]:
    order = len(elements)
    assert is_power_of_two(order)
    return [elements[reverse_bit_order(i, order)] for i in range(order)]
```

### Data extension

Implementations:

- [Python](https://github.com/protolambda/partial_fft/blob/master/das_fft.py)
- [Go](https://github.com/protolambda/go-kate/blob/master/das_extension.go)

```python
def das_fft_extension(data: Sequence[Point]) -> Sequence[Point]:
    """
    Given some even-index values of an IFFT input, compute the odd-index inputs,
    such that the second output half of the IFFT is all zeroes.
    """
    poly = inverse_fft(data)
    return fft(poly + [0]*len(poly))[1::2]
```

### Data recovery

See [Reed-Solomon erasure code recovery in `n*log^2(n)` time with FFTs](https://ethresear.ch/t/reed-solomon-erasure-code-recovery-in-n-log-2-n-time-with-ffts/3039) for theory.
Implementations:

- [Original Python](https://github.com/ethereum/research/blob/master/mimc_stark/recovery.py)
- [New optimized approach in python](https://github.com/ethereum/research/tree/master/polynomial_reconstruction)
- [Old approach in Go](https://github.com/protolambda/go-kzg/blob/master/legacy_recovery.go)

```python
def recover_data(data: Sequence[Optional[Sequence[Point]]]) -> Sequence[Point]:
    """Given a subset of half or more of subgroup-aligned ranges of values, recover the None values."""
    ...
```

## DAS functions

```python
def extend_data(data: Sequence[Point]) -> Sequence[Point]:
    """
    The input data gets reverse-bit-ordered, such that the first half of the final output matches the original data.
    We calculated the odd-index values with the DAS FFT extension, reverse-bit-order to put them in the second half.
    """
    rev_bit_odds = reverse_bit_order_list(das_fft_extension(reverse_bit_order_list(data)))
    return data + rev_bit_odds
```

```python
def unextend_data(extended_data: Sequence[Point]) -> Sequence[Point]:
    return extended_data[:len(extended_data)//2]
```

```python
def check_multi_kzg_proof(commitment: BLSCommitment, proof: BLSCommitment, x: Point, ys: Sequence[Point]) -> bool:
    """
    Run a KZG multi-proof check to verify that for the subgroup starting at x,
    the proof indeed complements the ys to match the commitment.
    """
    ...  # Omitted for now, refer to KZG implementation resources.
```

```python
def construct_proofs(extended_data_as_poly: Sequence[Point]) -> Sequence[BLSCommitment]:
    """
    Constructs proofs for samples of extended data (in polynomial form, 2nd half being zeroes).
    Use the FK20 multi-proof approach to construct proofs for a chunk length of POINTS_PER_SAMPLE.
    """
    ... # Omitted for now, refer to KZG implementation resources.
```

```python
def commit_to_data(data_as_poly: Sequence[Point]) -> BLSCommitment:
    """Commit to a polynomial by """
```

```python
def sample_data(slot: Slot, shard: Shard, extended_data: Sequence[Point]) -> Sequence[DASSample]:
    sample_count = len(extended_data) // POINTS_PER_SAMPLE
    assert sample_count <= MAX_SAMPLES_PER_BLOCK
    # get polynomial form of full extended data, second half will be all zeroes.
    poly = ifft(reverse_bit_order_list(extended_data))
    assert all(v == 0 for v in poly[len(poly)//2:])
    proofs = construct_proofs(poly)
    return [
        DASSample(
            slot=slot,
            shard=shard,
            # The proof applies to `x = w ** (reverse_bit_order(i, sample_count) * POINTS_PER_SAMPLE)`
            index=i,
            # The computed proofs match the reverse_bit_order_list(extended_data), undo that to get the right proof.
            proof=proofs[reverse_bit_order(i, sample_count)],
            # note: we leave the sample data as-is so it matches the original nicely.
            # The proof applies to `ys = reverse_bit_order_list(sample.data)`
            data=extended_data[i*POINTS_PER_SAMPLE:(i+1)*POINTS_PER_SAMPLE]
        ) for i in range(sample_count)
    ]
```

```python
def verify_sample(sample: DASSample, sample_count: uint64, commitment: BLSCommitment):
    domain_pos = reverse_bit_order(sample.index, sample_count)
    sample_root_of_unity = ROOT_OF_UNITY**MAX_SAMPLES_PER_BLOCK  # change point-level to sample-level domain
    x = sample_root_of_unity**domain_pos
    ys = reverse_bit_order_list(sample.data)
    assert check_multi_kzg_proof(commitment, sample.proof, x, ys)
```

```python
def reconstruct_extended_data(samples: Sequence[Optional[DASSample]]) -> Sequence[Point]:
    # Instead of recovering with a point-by-point approach, recover the samples by recovering missing subgroups.
    subgroups = [None if sample is None else reverse_bit_order_list(sample.data) for sample in samples]
    return recover_data(subgroups)
```
