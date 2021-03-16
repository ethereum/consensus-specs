# Test format: BLS sign message

Message signing with BLS should produce a signature.

## Test case format

### `meta.yaml`

```yaml
release_version: string  -- required, the pyspec release version.
```

### `data.yaml`

```yaml
input:
  privkey: bytes32 -- the private key used for signing
  message: bytes32 -- input message to sign (a hash)
output: BLS Signature -- expected output, single BLS signature or empty.
```

All byte(s) fields are encoded as strings, hexadecimal encoding, prefixed with `0x`.
