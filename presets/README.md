# Presets

Presets are more extensive than runtime configurations, and generally only applicable during compile-time.
Each preset is defined as a directory, with YAML files per fork.

Configurations can extend a preset by setting the `PRESET_BASE` variable.
An implementation may choose to only support 1 preset per build-target and should validate
the `PRESET_BASE` variable in the config matches the running build.

Standard presets:
- [`mainnet/`](./mainnet): Used in mainnet, mainnet-like testnets (e.g. Hoodi), and spec-testing
- [`minimal/`](./minimal): Used in low-resource local dev testnets, and spec-testing

Client implementers may opt to support additional presets, e.g. for extra large beacon states for benchmarking.
See [`/configs/`](../configs) for run-time configuration, e.g. to configure a new testnet.

## Forking

Like the [config forking](../configs/README.md#forking),
the preset extends with every fork, instead of overwriting previous values.
An implementation can ignore preset files as a whole for future forks,
and can thus implement stricter compile-time warnings on unrecognized or missing variables in current forks.

## Format

The preset format matches the [config format](../configs/README.md#format).
