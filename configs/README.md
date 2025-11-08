# Configurations

This directory contains a set of configurations used for testing, testnets, and
mainnet. A client binary may be compiled for a specific `PRESET_BASE`, and then
load different configurations around that preset to participate in different
networks or tests.

Standard configs:

- [`mainnet.yaml`](./mainnet.yaml): Mainnet configuration
- [`minimal.yaml`](./minimal.yaml): Minimal configuration, used in spec-testing
  along with the [`minimal`](../presets/minimal) preset.

Not all network configurations are in scope for the specification, see
[`github.com/eth-clients/eth2-networks`](https://github.com/eth-clients/eth2-networks)
for common networks, and additional testnet assets.

## Forking

Variables are not replaced but extended with forks. This is to support syncing
from one state to another over a fork boundary, without hot-swapping a config.
Instead, for forks that introduce changes in a variable, the variable name is
suffixed with the fork name, e.g. `INACTIVITY_PENALTY_QUOTIENT_ALTAIR`.

Future-fork variables can be ignored, e.g. ignore Sharding variables as a client
that only supports Phase 0 currently.

Over time, the need to sync an older state may be deprecated. In this case, the
suffix on the new variable may be removed, and the old variable will keep a
special name before completely being removed.

A previous iteration of forking made use of "timelines", but this collides with
the definitions used in the spec (variables for special forking slots, etc.),
and was not integrated sufficiently in any of the spec tools or implementations.
Instead, the config essentially doubles as fork definition now, e.g. changing
the value for `ALTAIR_FORK_EPOCH` changes the fork.

## Format

Each preset and configuration is a key-value mapping.

**Key**: an `UPPER_SNAKE_CASE` (a.k.a. "macro case") formatted string, name of
the variable.

**Value** can be either:

- an unsigned integer number, can be up to 64 bits (incl.)
- a hexadecimal string, prefixed with `0x`

This format is fully YAML compatible. The presets and configurations may contain
comments to describe the values.

## Configuration Variables

Configuration files contain various types of variables:

- **Fork Epochs**: Define when forks activate (e.g., `ALTAIR_FORK_EPOCH`)
- **Fork Versions**: Define fork version identifiers (e.g., `ALTAIR_FORK_VERSION`)
- **Network Parameters**: Define network-specific settings
- **Time Parameters**: Define timing-related constants
- **Validator Parameters**: Define validator-related settings

## Best Practices

When creating or modifying configurations:

1. **Use Comments**: Add descriptive comments explaining the purpose of each variable
2. **Follow Naming Conventions**: Use `UPPER_SNAKE_CASE` for all variable names
3. **Validate Values**: Ensure values are within expected ranges
4. **Test Changes**: Always test configuration changes with minimal preset first
5. **Document Changes**: Document any custom modifications or additions