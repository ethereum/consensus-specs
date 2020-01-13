# Test format: BLS hash-uncompressed

A BLS uncompressed-hash to G2.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  message: bytes32
  domain: bytes8   -- the BLS domain
output: List[List[bytes48]] -- 3 lists, each a length of two
```

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with `0x`.


## Condition

The `msg_hash_g2_uncompressed` handler should hash the `message`, with the given `domain`, to G2, without compression, and the result should match the expected `output`.
