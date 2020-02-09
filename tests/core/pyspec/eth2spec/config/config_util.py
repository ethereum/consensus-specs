from ruamel.yaml import YAML
from pathlib import Path
from os.path import join
from typing import Dict, Any

config: Dict[str, Any] = {}


# Access to overwrite spec constants based on configuration
# This is called by the spec module after declaring its globals, and applies the loaded presets.
def apply_constants_config(spec_globals: Dict[str, Any]) -> None:
    global config
    for k, v in config.items():
        if k.startswith('DOMAIN_'):
            spec_globals[k] = spec_globals['DomainType'](v)  # domain types are defined as bytes in the configs
        else:
            spec_globals[k] = v


# Load presets from a file, and then prepares the global config setting. This does not apply the config.
# To apply the config, reload the spec module (it will re-initialize with the config taken from here).
def prepare_config(configs_path, config_name):
    global config
    config = load_config_file(configs_path, config_name)


def load_config_file(configs_dir, presets_name) -> Dict[str, Any]:
    """
    Loads the given preset
    :param presets_name: The name of the presets. (lowercase snake_case)
    :return: Dictionary, mapping of constant-name -> constant-value
    """
    path = Path(join(configs_dir, presets_name + '.yaml'))
    yaml = YAML(typ='base')
    loaded = yaml.load(path)
    out = dict()
    for k, v in loaded.items():
        if isinstance(v, list):
            out[k] = v
        elif isinstance(v, str) and v.startswith("0x"):
            out[k] = bytes.fromhex(v[2:])
        else:
            out[k] = int(v)
    return out
