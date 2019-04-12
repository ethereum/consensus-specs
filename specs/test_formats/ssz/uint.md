# Test format: SSZ uints

SSZ supports encoding of uints up to 32 bytes. These are considered to be basic types.

## Test case format

```yaml
TODO: old format
# type: "uintN"      -- string, where N is one of [8, 16, 32, 64, 128, 256]
# valid: bool        -- expected validity of the input data
# ssz: bytes         -- string, input data, hex encoded, with prefix 0x
# tags: List[string] -- description of test case, in the form of a list of labels
```

## Condition

- Encoding: After encoding the given input number, the
- Decoding: After decoding the given `output` bytes, it should match the `input` number  

## Forks

Forks-interpretation: `collective` 

```

```