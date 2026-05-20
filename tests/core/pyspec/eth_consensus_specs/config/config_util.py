from collections.abc import Iterable
from pathlib import Path
from typing import Any, BinaryIO, TextIO

from ruamel.yaml import YAML


def parse_config_vars(conf: dict[str, Any]) -> dict[str, Any]:
    """
    Parses a dict of basic str/int/list/dict types into more detailed python types.
    """

    def parse_value(k: str, v: Any, in_list: bool = False) -> Any:
        if isinstance(v, list):
            return [parse_value(k, item, in_list=True) for item in v]
        if isinstance(v, dict):
            return {
                item_key: parse_value(item_key, item_value) for item_key, item_value in v.items()
            }
        if isinstance(v, str) and v.startswith("0x"):
            return bytes.fromhex(v[2:])
        if k != "PRESET_BASE" and k != "CONFIG_NAME":
            if in_list and isinstance(v, str) and not v.isdigit():
                return v
            return int(v)
        return v

    out: dict[str, Any] = dict()
    for k, v in conf.items():
        out[k] = parse_value(k, v)
    return out


def load_preset(preset_files: Iterable[Path | BinaryIO | TextIO]) -> dict[str, Any]:
    """
    Loads a directory of preset files, merges the result into one preset.
    """
    preset = {}
    for fork_file in preset_files:
        yaml = YAML(typ="base")
        fork_preset: dict = yaml.load(fork_file)
        if fork_preset is None:  # for empty YAML files
            continue
        if not set(fork_preset.keys()).isdisjoint(preset.keys()):
            duplicates = set(fork_preset.keys()).intersection(set(preset.keys()))
            raise Exception(f"duplicate config var(s) in preset files: {', '.join(duplicates)}")
        preset.update(fork_preset)
    assert preset != {}
    return parse_config_vars(preset)


def load_config_file(config_path: Path | BinaryIO | TextIO) -> dict[str, Any]:
    """
    Loads the given configuration file.
    """
    yaml = YAML(typ="base")
    config_data = yaml.load(config_path)
    return parse_config_vars(config_data)


mainnet_config_data: dict[str, Any]
minimal_config_data: dict[str, Any]
loaded_defaults = False


def load_defaults(spec_configs_path: Path) -> None:
    global mainnet_config_data, minimal_config_data

    mainnet_config_data = load_config_file(spec_configs_path / "mainnet.yaml")
    minimal_config_data = load_config_file(spec_configs_path / "minimal.yaml")

    global loaded_defaults
    loaded_defaults = True
