from pathlib import Path
import json


from ruamel.yaml import (
    YAML,
)
from snappy import decompress

from eth2spec.debug.encode import encode


def load_file(file_path, mode='r'):
    try:
        with open(file_path, mode) as file:
            data = file.read()
            return data
    except FileNotFoundError:
        print(f"[Error] File {file_path} not found.")
        exit()


def get_ssz_object_from_json_file(container, file_path):
    with open(Path(file_path), 'r') as f:
        json_data = json.load(f)
    return container.from_obj(json_data['data'])


def get_state_from_json_file(spec, file_path):
    return get_ssz_object_from_json_file(spec.BeaconState, file_path)


def get_ssz_object_from_ssz_encoded(container, file_path, is_snappy=True):
    state_bytes = load_file(Path(file_path), mode='rb')
    if is_snappy:
        state_bytes = decompress(state_bytes)
    return container.decode_bytes(state_bytes)


def get_state_from_ssz_encoded(spec, file_path, is_snappy=True):
    return get_ssz_object_from_ssz_encoded(spec.BeaconState, file_path, is_snappy=is_snappy)


def output_ssz_to_file(output_dir, value, dump_yaml_fn):
    # output full data to file
    yaml = YAML(pure=True)
    yaml.default_flow_style = None
    output_dir = Path(output_dir)
    output_part(output_dir, dump_yaml_fn(
        data=encode(value), name='output', file_mode="w", yaml_encoder=yaml))


# TODO: This function will be extracted in `gen_runner.py` in https://github.com/ethereum/consensus-specs/pull/3347
def output_part(case_dir, fn):
    # make sure the test case directory is created before any test part is written.
    case_dir.mkdir(parents=True, exist_ok=True)
    fn(case_dir)


# FIXME: duplicate to `gen_runner.py` function
def dump_yaml_fn(data, name, file_mode, yaml_encoder):
    def dump(case_path: Path):
        out_path = case_path / Path(name + '.yaml')
        with out_path.open(file_mode) as f:
            yaml_encoder.dump(data, f)
    return dump
