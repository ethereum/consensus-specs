from preset_loader import loader
from typing import Dict, Any

presets: Dict[str, Any] = {}


# Access to overwrite spec constants based on configuration
# This is called by the spec module after declaring its globals, and applies the loaded presets.
def apply_constants_preset(spec_globals: Dict[str, Any]) -> None:
    global presets
    for k, v in presets.items():
        if k.startswith('DOMAIN_'):
            spec_globals[k] = spec_globals['DomainType'](v)  # domain types are defined as bytes in the configs
        else:
            spec_globals[k] = v


# Load presets from a file. This does not apply the presets.
# To apply the presets, reload the spec module (it will re-initialize with the presets taken from here).
def load_presets(configs_path, config_name):
    global presets
    presets = loader.load_presets(configs_path, config_name)
