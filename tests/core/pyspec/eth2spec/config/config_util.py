from ruamel.yaml import YAML
from pathlib import Path
from os.path import join
from typing import Dict, Any

config: Dict[str, Any] = {}


# Access to overwrite spec constants based on configuration
# This is called by the spec module after declaring its globals, and applies the loaded presets.
def apply_constants_config(spec_globals: Dict[str, Any], warn_if_unknown: bool = False) -> None:
    global config
    for k, v in config.items():
        # the spec should have default values for everything, if not, the config key is invalid.
        if k in spec_globals:
            # Keep the same type as the default value indicates (which may be an SSZ basic type subclass, e.g. 'Gwei')
            spec_globals[k] = spec_globals[k].__class__(v)
        else:
            # Note: Phase 0 spec will not know the phase 1 config values.
            # Yet, during debugging you can enable explicit warnings.
            if warn_if_unknown:
                print(f"WARNING: unknown config key: '{k}' with value: '{v}'")


# Load presets from a file, and then prepares the global config setting. This does not apply the config.
# To apply the config, reload the spec module (it will re-initialize with the config taken from here).
def prepare_config(configs_path: str, config_name: str) -> None:
    global config
    config = load_config_file(configs_path, config_name)


def load_config_file(configs_dir: str, presets_name: str) -> Dict[str, Any]:
    """
    Loads the given preset
    :param presets_name: The name of the presets. (lowercase snake_case)
    :return: Dictionary, mapping of constant-name -> constant-value
    """
    path = Path(join(configs_dir, presets_name + '.yaml'))
    yaml = YAML(typ='base')
    loaded = yaml.load(path)
    out: Dict[str, Any] = dict()
    for k, v in loaded.items():
        if isinstance(v, list):
            # Clean up integer values. YAML parser renders lists of ints as list of str
            out[k] = [int(item) if item.isdigit() else item for item in v]
        elif isinstance(v, str) and v.startswith("0x"):
            out[k] = bytes.fromhex(v[2:])
        else:
            out[k] = int(v)
    return out
