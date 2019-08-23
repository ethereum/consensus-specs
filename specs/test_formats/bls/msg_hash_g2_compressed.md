# Test format: BLS hash-compressed

A BLS compressed-hash to G2.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input: 
  message: bytes32
  domain: bytes8   -- the BLS domain
output: List[bytes48] -- length of two
```

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with `0x`.


## Condition

The `msg_hash_g2_compressed` handler should hash the `message`, with the given `domain`, to G2 with compression, and the result should match the expected `output`.
