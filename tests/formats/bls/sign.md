# Test format: BLS sign message

Message signing with BLS should produce a signature.

## Test case format

The test data is declared in a `data.yaml` file:

```yaml
input:
  privkey: bytes32 -- the private key used for signing
  message: bytes32 -- input message to sign (a hash)
output: BLS Signature -- expected output, single BLS signature or `null`.
```

- All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with
  `0x`.
- output value is `null` if the input is invalid.

## Condition

The `sign` handler should sign `message` with `privkey`, and the resulting
signature should match the expected `output`.
