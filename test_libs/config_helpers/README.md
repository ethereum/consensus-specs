# ETH 2.0 config helpers

`preset_loader`: A util to load constants-presets with.
See [Constants-presets documentation](../../configs/constants_presets/README.md).

Usage:

```python
configs_path = 'configs/'

...

import preset_loader
from eth2spec.phase0 import spec
my_presets = preset_loader.load_presets(configs_path, 'main_net')
spec.apply_constants_preset(my_presets)
```

WARNING: this overwrites globals, make sure to prevent accidental collisions with other usage of the same imported specs package.
