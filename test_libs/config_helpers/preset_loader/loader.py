from typing import Dict, Any

from ruamel.yaml import (
    YAML,
)
from pathlib import Path
from os.path import join


def load_presets(configs_dir, presets_name) -> Dict[str, Any]:
    """
    Loads the given preset
    :param presets_name: The name of the generator. (lowercase snake_case)
    :return: Dictionary, mapping of constant-name -> constant-value
    """
    path = Path(join(configs_dir, 'constant_presets', presets_name+'.yaml'))
    yaml = YAML(typ='safe')
    return yaml.load(path)
