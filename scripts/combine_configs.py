from pathlib import Path
import sys

from ruamel.yaml import YAML

from eth2spec.test.helpers.constants import ALL_CONFIGS, TESTGEN_FORKS
from eth2spec.config.config_util import get_loaded_config


cwd = Path.cwd()
typ = 'rt'


def main(argv):
    yaml = YAML(typ=typ)
    for config in ALL_CONFIGS:
        result = get_loaded_config('./configs/', config, typ=typ, specs=TESTGEN_FORKS)
        result.pop('CONFIG_NAME')

    if len(argv) == 0:
        for config in ALL_CONFIGS:
            for spec in TESTGEN_FORKS:
                combined_file = Path(cwd / f'./configs/combined/{config}/{spec}.yaml')
                with combined_file.open("w") as f:
                    yaml.dump(result, f)
                print(f"Generated {combined_file}")
    elif len(argv) == 1 and argv[0] == 'check':
        for config in ALL_CONFIGS:
            for spec in TESTGEN_FORKS:
                combined_file = Path(cwd / f'./configs/combined/{config}/{spec}.yaml')
                with combined_file.open("r") as f:
                    loaded = yaml.load(f)
                    assert loaded == result
                    print(f"Checked {combined_file}")
    else:
        raise Exception('No such command: %s', argv)


if __name__ == '__main__':
    main(sys.argv[1:])
