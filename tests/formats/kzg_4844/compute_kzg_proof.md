# Test format: Compute KZG proof

Compute the KZG proof for a given `blob` and an evaluation point `z`.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  blob: Blob -- the data blob representing a polynomial
  z: Bytes32 -- bytes encoding the BLS field element at which the polynomial should be evaluated
output: Tuple[KZGProof, Bytes32] -- The KZG proof and the value y = f(z)
```

- `blob` here is encoded as a string: hexadecimal encoding of
  `4096 * 32 = 131072` bytes, prefixed with `0x`.
- `z` here is encoded as a string: hexadecimal encoding of `32` bytes
  representing a big endian encoded field element, prefixed with `0x`.
- `y` here is encoded as a string: hexadecimal encoding of `32` bytes
  representing a big endian encoded field element, prefixed with `0x`.

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with
`0x`.

## Condition

The `compute_kzg_proof` handler should compute the KZG proof as well as the
value `y` for evaluating the polynomial represented by `blob` at `z`, and the
result should match the expected `output`. If the blob is invalid (e.g.
incorrect length or one of the 32-byte blocks does not represent a BLS field
element) or `z` is not a valid BLS field element, it should error, i.e. the
output should be `null`.
