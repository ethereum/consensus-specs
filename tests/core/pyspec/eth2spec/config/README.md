# Eth2 config util

For configuration, see [Configs documentation](../../../../../configs/README.md).

## Usage:

```python
from eth2spec.config import config_util
from eth2spec.phase0.mainnet import as spec
from pathlib import Path

# To load the default configurations
config_util.load_defaults(Path("eth2.0-specs/configs"))  # change path to point to equivalent of specs `configs` dir.
# After loading the defaults, a config can be chosen: 'mainnet', 'minimal', or custom network config (by file path)
spec.config = spec.Configuration(**config_util.load_config_file('mytestnet.yaml'))
```

Note: previously the testnet config files included both preset and runtime-configuration data.
The new config loader is compatible with this: all config vars are loaded from the file, 
but those that have become presets will be ignored. 
