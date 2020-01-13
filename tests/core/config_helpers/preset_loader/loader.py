from typing import Dict, Any

from ruamel.yaml import (
    YAML,
)
from pathlib import Path
from os.path import join


def load_presets(configs_dir, presets_name) -> Dict[str, Any]:
    """
    Loads the given preset
    :param presets_name: The name of the presets. (lowercase snake_case)
    :return: Dictionary, mapping of constant-name -> constant-value
    """
    path = Path(join(configs_dir, presets_name+'.yaml'))
    yaml = YAML(typ='base')
    loaded = yaml.load(path)
    out = dict()
    for k, v in loaded.items():
        if v.startswith("0x"):
            out[k] = bytes.fromhex(v[2:])
        else:
            out[k] = int(v)
    return out
