import os
from pathlib import Path
from copy import deepcopy
from typing import Dict, Iterable, Union, BinaryIO, TextIO, Literal, Any
from ruamel.yaml import YAML

# This holds the full config (both runtime config and compile-time preset), for specs to initialize
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


# Load YAML configuration from a file path or input, or pick the default 'mainnet' and 'minimal' configs.
# This prepares the global config memory. This does not apply the config.
# To apply the config, reload the spec module (it will re-initialize with the config taken from here).
def prepare_config(config_path: Union[Path, BinaryIO, TextIO, Literal['mainnet'], Literal['minimal']]) -> None:
    # Load the configuration, and try in-memory defaults.
    if config_path == 'mainnet':
        conf_data = deepcopy(mainnet_config_data)
    elif config_path == 'minimal':
        conf_data = deepcopy(minimal_config_data)
    else:
        conf_data = load_config_file(config_path)
    # Check the configured preset
    base = conf_data['PRESET_BASE']
    if base not in ('minimal', 'mainnet'):
        raise Exception(f"unknown PRESET_BASE: {base}")
    # Apply configuration if everything checks out
    global config
    config = deepcopy(mainnet_preset_data if base == 'mainnet' else minimal_preset_data)
    config.update(conf_data)


def parse_config_vars(conf: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses a dict of basic str/int/list types into more detailed python types
    """
    out: Dict[str, Any] = dict()
    for k, v in conf.items():
        if isinstance(v, list):
            # Clean up integer values. YAML parser renders lists of ints as list of str
            out[k] = [int(item) if item.isdigit() else item for item in v]
        elif isinstance(v, str) and v.startswith("0x"):
            out[k] = bytes.fromhex(v[2:])
        elif k != 'PRESET_BASE':
            out[k] = int(v)
        else:
            out[k] = v
    return out


def load_preset(preset_files: Iterable[Union[Path, BinaryIO, TextIO]]) -> Dict[str, Any]:
    """
    Loads the a directory of preset files, merges the result into one preset.
    """
    preset = {}
    for fork_file in preset_files:
        yaml = YAML(typ='base')
        fork_preset: dict = yaml.load(fork_file)
        if fork_preset is None:  # for empty YAML files
            continue
        if not set(fork_preset.keys()).isdisjoint(preset.keys()):
            duplicates = set(fork_preset.keys()).intersection(set(preset.keys()))
            raise Exception(f"duplicate config var(s) in preset files: {', '.join(duplicates)}")
        preset.update(fork_preset)
    assert preset != {}
    return parse_config_vars(preset)


def load_config_file(config_path: Union[Path, BinaryIO, TextIO]) -> Dict[str, Any]:
    """
    Loads the given configuration file.
    """
    yaml = YAML(typ='base')
    config_data = yaml.load(config_path)
    return parse_config_vars(config_data)


# Can't load these with pkg_resources, because the files are not in a package (requires `__init__.py`).
mainnet_preset_data: Dict[str, Any]
minimal_preset_data: Dict[str, Any]
mainnet_config_data: Dict[str, Any]
minimal_config_data: Dict[str, Any]
loaded_defaults = False


def load_defaults(spec_configs_path: Path) -> None:
    global mainnet_preset_data, minimal_preset_data, mainnet_config_data, minimal_config_data

    _, _, mainnet_preset_file_names = next(os.walk(spec_configs_path / 'mainnet_preset'))
    mainnet_preset_data = load_preset([spec_configs_path / 'mainnet_preset' / p for p in mainnet_preset_file_names])
    _, _, minimal_preset_file_names = next(os.walk(spec_configs_path / 'minimal_preset'))
    minimal_preset_data = load_preset([spec_configs_path / 'minimal_preset' / p for p in minimal_preset_file_names])
    mainnet_config_data = load_config_file(spec_configs_path / 'mainnet_config.yaml')
    minimal_config_data = load_config_file(spec_configs_path / 'minimal_config.yaml')

    global loaded_defaults
    loaded_defaults = True
