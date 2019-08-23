# Test format: BLS private key to pubkey

A BLS private key to public key conversion.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input: bytes32 -- the private key
output: bytes48 -- the public key
```

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with `0x`.


## Condition

The `priv_to_pub` handler should compute the public key for the given private key `input`, and the result should match the expected `output`.
