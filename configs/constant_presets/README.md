# Constant Presets

This directory contains a set of constants presets used for testing, testnets, and mainnet.

A preset file contains all the constants known for its target.
Later-fork constants can be ignored, e.g. ignore phase1 constants as a client that only supports phase 0 currently.

## Format

Each preset is a key-value mapping.

**Key**: an `UPPER_SNAKE_CASE` (a.k.a. "macro case") formatted string, name of the constant.
**Value**: can be any of:
 - an unsigned integer number, can be up to 64 bits (incl.)
 - a hexadecimal string, prefixed with `0x`

Presets may contain comments to describe the values.

See `mainnet.yaml` for a complete example.

