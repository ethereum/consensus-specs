from pathlib import Path
from typing import Dict, Iterable, Union, BinaryIO, TextIO, Any
from ruamel.yaml import YAML


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
        elif k != "PRESET_BASE" and k != "CONFIG_NAME":
            out[k] = int(v)
        else:
            out[k] = v
    return out


def load_preset(
    preset_files: Iterable[Union[Path, BinaryIO, TextIO]]
) -> Dict[str, Any]:
    """
    Loads the a directory of preset files, merges the result into one preset.
    """
    preset = {}
    for fork_file in preset_files:
        yaml = YAML(typ="base")
        fork_preset: dict = yaml.load(fork_file)
        if fork_preset is None:  # for empty YAML files
            continue
        if not set(fork_preset.keys()).isdisjoint(preset.keys()):
            duplicates = set(fork_preset.keys()).intersection(set(preset.keys()))
            raise Exception(
                f"duplicate config var(s) in preset files: {', '.join(duplicates)}"
            )
        preset.update(fork_preset)
    assert preset != {}
    return parse_config_vars(preset)


def load_config_file(config_path: Union[Path, BinaryIO, TextIO]) -> Dict[str, Any]:
    """
    Loads the given configuration file.
    """
    yaml = YAML(typ="base")
    config_data = yaml.load(config_path)
    return parse_config_vars(config_data)


mainnet_config_data: Dict[str, Any]
minimal_config_data: Dict[str, Any]
loaded_defaults = False


def load_defaults(spec_configs_path: Path) -> None:
    global mainnet_config_data, minimal_config_data

    mainnet_config_data = load_config_file(spec_configs_path / "mainnet.yaml")
    minimal_config_data = load_config_file(spec_configs_path / "minimal.yaml")

    global loaded_defaults
    loaded_defaults = True
