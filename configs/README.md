# Configs

This directory contains a set of constants presets used for testing, testnets, and mainnet.

A preset file contains all the constants known for its target.
Later-fork constants can be ignored, e.g. ignore Phase 1 constants as a client that only supports Phase 0 currently.


## Forking

Configs are not replaced, but extended with forks. This is to support syncing from one state to the other over a fork boundary, without hot-swapping a config.
Instead, for forks that introduce changes in a constant, the constant name is prefixed with a short abbreviation of the fork.

Over time, the need to sync an older state may be deprecated.
In this case, the prefix on the new constant may be removed, and the old constant will keep a special name before completely being removed.

A previous iteration of forking made use of "timelines", but this collides with the definitions used in the spec (constants for special forking slots, etc.), and was not integrated sufficiently in any of the spec tools or implementations.
Instead, the config essentially doubles as fork definition now, e.g. changing the value for `PHASE_1_FORK_SLOT` changes the fork.

Another reason to prefer forking through constants is the ability to program a forking moment based on context, instead of being limited to a static slot number.

 
## Format

Each preset is a key-value mapping.

**Key**: an `UPPER_SNAKE_CASE` (a.k.a. "macro case") formatted string, name of the constant.

**Value** can be either:
 - an unsigned integer number, can be up to 64 bits (incl.)
 - a hexadecimal string, prefixed with `0x`

Presets may contain comments to describe the values.

See [`mainnet_phase0.yaml`](./mainnet_phase0.yaml) for a complete example.
