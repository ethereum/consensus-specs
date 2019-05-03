# Test format: BLS signature aggregation

A BLS signature aggregation combines a series of signatures into a single signature.

## Test case format

```yaml
input: List[BLS Signature] -- list of input BLS signatures
output: BLS Signature -- expected output, single BLS signature
```

`BLS Signature` here is encoded as a string: hexadecimal encoding of 96 bytes (192 nibbles), prefixed with `0x`.


## Condition

The `aggregate_sigs` handler should aggregate the signatures in the `input`, and the result should match the expected `output`.
