# Test format: BLS pubkey aggregation

A BLS pubkey aggregation combines a series of pubkeys into a single pubkey.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input: List[BLS Pubkey] -- list of input BLS pubkeys
output: BLS Pubkey -- expected output, single BLS pubkey
```

`BLS Pubkey` here is encoded as a string: hexadecimal encoding of 48 bytes (96 nibbles), prefixed with `0x`.


## Condition

The `aggregate_pubkeys` handler should aggregate the keys in the `input`, and the result should match the expected `output`.
