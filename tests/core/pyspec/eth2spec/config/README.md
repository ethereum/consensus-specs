# Eth2 config util

For configuration, see [Configs documentation](../../../../../configs/README.md).

## Usage:

```python
configs_path = 'configs/'

...

from eth2spec.config import config_util
from eth2spec.phase0 import spec
from importlib import reload
config_util.prepare_config(configs_path, 'mainnet')
# reload spec to make loaded config effective
reload(spec)
```

WARNING: this overwrites globals, make sure to prevent accidental collisions with other usage of the same imported specs package.
