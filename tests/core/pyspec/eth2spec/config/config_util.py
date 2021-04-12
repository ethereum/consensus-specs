import os
from pathlib import Path
from typing import Dict, Any, Optional, Sequence

from ruamel.yaml import YAML

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
            # Note: The phase 0 spec will not warn if Altair or later config values are applied.
            # During debugging you can enable explicit warnings.
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
    :param configs_dir: the folder of config files
    :param presets_name: The name of the presets. (lowercase snake_case)
    :return: Dictionary, mapping of constant-name -> constant-value
    """
    loaded_config = get_loaded_config(configs_dir, presets_name, 'base')

    out: Dict[str, Any] = dict()
    for k, v in loaded_config.items():
        if isinstance(v, list):
            # Clean up integer values. YAML parser renders lists of ints as list of str
            out[k] = [int(item) if item.isdigit() else item for item in v]
        elif isinstance(v, str) and v.startswith("0x"):
            out[k] = bytes.fromhex(v[2:])
        elif k == "CONFIG_NAME":
            out[k] = str(v)
        else:
            out[k] = int(v)
    return out


def get_loaded_config(configs_dir: str,
                      presets_name: str,
                      typ: str,
                      specs: Optional[Sequence] = None) -> Dict[str, Any]:
    """
    Loads the given preset
    :param configs_dir: the folder of config files
    :param presets_name: The name of the presets. (lowercase snake_case)
    :param typ: YAML decoder type
    :param specs: only load specific spec versions
    :return: Dictionary, mapping of constant-name -> constant-value
    """
    present_dir = Path(configs_dir) / presets_name
    _, _, config_files = next(os.walk(present_dir))
    config_files.sort()
    if specs is not None:
        config_files = list(filter(lambda config_file: config_file[:-5] in specs, config_files))
    loaded_config = {}
    for config_file_name in config_files:
        yaml = YAML(typ=typ)
        path = present_dir / config_file_name
        loaded = yaml.load(path)
        loaded_config.update(loaded)
    assert loaded_config != {}

    return loaded_config
