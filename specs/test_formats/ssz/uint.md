# Test format: SSZ uints

SSZ supports encoding of uints up to 32 bytes. These are considered to be basic types.

## Test case format

```yaml
type: "uintN"      -- string, where N is one of [8, 16, 32, 64, 128, 256]
valid: bool        -- expected validity of the input data
value: string      -- string, decimal encoding, to support up to 256 bit integers
ssz: bytes         -- string, input data, hex encoded, with prefix 0x
tags: List[string] -- description of test case, in the form of a list of labels
```

## Condition

Two-way testing can be implemented in the test-runner:
- Encoding: After encoding the given input number `value`, the output should match `ssz`
- Decoding: After decoding the given `ssz` bytes, it should match the input number `value` 

## Forks

Forks-interpretation: `collective` 
