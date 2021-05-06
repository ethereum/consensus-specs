# Presets & Configurations

This directory contains a set of presets and configurations used for testing, testnets, and mainnet.

**Presets** are for deeper customization for different modes of operation, compile-time changes.
**Configurations** are intended for different network configurations, fully runtime-configurable.

Later-fork variables can be ignored, e.g. ignore Sharding variables as a client that only supports Phase 0 currently.


## Forking

Variables are not replaced, but extended with forks. This is to support syncing from one state to the other over a fork boundary, without hot-swapping a config.
Instead, for forks that introduce changes in a variable, the variable name is prefixed with a short abbreviation of the fork.

Over time, the need to sync an older state may be deprecated.
In this case, the prefix on the new variable may be removed, and the old variable will keep a special name before completely being removed.

A previous iteration of forking made use of "timelines", but this collides with the definitions used in the spec (variables for special forking slots, etc.), and was not integrated sufficiently in any of the spec tools or implementations.
Instead, the config essentially doubles as fork definition now, e.g. changing the value for `ALTAIR_FORK_EPOCH` changes the fork.
 
## Format

Each preset and configuration is a key-value mapping.

**Key**: an `UPPER_SNAKE_CASE` (a.k.a. "macro case") formatted string, name of the variable.

**Value** can be either:
 - an unsigned integer number, can be up to 64 bits (incl.)
 - a hexadecimal string, prefixed with `0x`

This format is fully YAML compatible.
The presets and configurations may contain comments to describe the values.

## Presets

Presets are more extensive than runtime configurations, and generally only applicable during compile-time.
Each preset is defined as a directory, with YAML files per fork.
Configurations can extend a preset by setting the `PRESET_BASE` variable.
An implementation may choose to only support 1 preset per build-target and should validate this `PRESET_BASE` variable.

See: [`mainnet_preset/`](./mainnet_preset) and [`minimal_preset/`](./minimal_preset).

## Configuration

Configurations are more minimal, singular YAML files, to define different network definitions.
Besides different (test-)network definitions, implementations also apply these during runtime for spec-tests.

See: [`mainnet_config.yaml`](./mainnet_config.yaml) and [`minimal_config.yaml`](./minimal_config.yaml).
