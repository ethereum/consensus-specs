# Eth2 config util

For configuration, see [Configs documentation](../../../../../configs/README.md).

## Usage:

```python
from eth2spec.config import config_util
from eth2spec.phase0 import spec
from importlib import reload
from pathlib import Path

# To load the presets and configurations
config_util.load_defaults(Path("eth2.0-specs/configs"))  # change path to point to equivalent of specs `configs` dir.
# After loading the defaults, a config can be chosen: 'mainnet', 'minimal', or custom network config
config_util.prepare_config('minimal')
# Alternatively, load a custom testnet config:
config_util.prepare_config('my_config.yaml')
# reload spec to make loaded config effective
reload(spec)
```

Note: previously the testnet config files included both preset and runtime-configuration data.
The new config loader is compatible with this: just run `prepare_config` without loading preset defaults,
and omit the `PRESET_BASE` from the config.

WARNING: this overwrites globals, make sure to prevent accidental collisions with other usage of the same imported specs package.
