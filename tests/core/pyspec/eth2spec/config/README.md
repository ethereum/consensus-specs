<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Consensus specs config util](#consensus-specs-config-util)
  - [Config usage:](#config-usage)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Consensus specs config util

For run-time configuration, see [Configs documentation](../../../../../configs/README.md).

For compile-time presets, see [Presets documentation](../../../../../presets/README.md)
and the `build-targets` flag for the `pyspec` distutils command.

## Config usage:

```python
from eth2spec.config import config_util
from eth2spec.phase0 import mainnet as spec
from pathlib import Path

# To load the default configurations
config_util.load_defaults(Path("consensus-specs/configs"))  # change path to point to equivalent of specs `configs` dir.
# After loading the defaults, a config can be chosen: 'mainnet', 'minimal', or custom network config (by file path)
spec.config = spec.Configuration(**config_util.load_config_file(Path('mytestnet.yaml')))
```

Note: previously the testnet config files included both preset and runtime-configuration data.
The new config loader is compatible with this: all config vars are loaded from the file, 
but those that have become presets can be ignored. 
