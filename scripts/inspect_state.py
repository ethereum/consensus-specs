from eth2spec.test.context import spec_targets
from eth2spec.debug.encode import encode
from eth2spec.debug.tools import (
    get_state_from_json_file,
    get_state_from_ssz_encoded,
    dump_yaml_fn,
    output_ssz_to_file,
)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--state-path",
        dest="state_path",
        required=True,
        help='the snappy-ed state file path',
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="output_dir",
        required=True,
        help='the output directory',
    )
    parser.add_argument(
        "--fork",
        dest="fork",
        default='capella',
        help='the version of the state',
    )
    parser.add_argument(
        "--preset",
        dest="preset",
        default='mainnet',
        help='the version of the state',
    )
    parser.add_argument(
        "--field",
        dest="field",
        required=False,
        help='specific field',
    )
    parser.add_argument(
        "--is-snappy",
        dest="is_snappy",
        help='is snappy compressed',
        action='store_true',  # False by default
    )
    parser.add_argument(
        "--is-json",
        dest="is_json",
        help='is JSON file from REST API',
        action='store_true',  # False by default
    )
    args = parser.parse_args()
    state_path = args.state_path
    output_dir = args.output_dir
    preset = args.preset
    fork = args.fork
    field = args.field
    is_snappy = args.is_snappy
    is_json = args.is_json

    try:
        spec = spec_targets[preset][fork]
    except KeyError as e:
        print(f'[Error] Wrong key {preset} or {fork}:')
        print(e)
        exit()

    if is_json:
        state = get_state_from_json_file(spec, file_path=state_path)
    else:
        state = get_state_from_ssz_encoded(spec, file_path=state_path, is_snappy=is_snappy)

    # Output specific field to file
    if field is not None and field in state.fields():
        value = state.__getattr__(field)
        output_ssz_to_file(output_dir, value, dump_yaml_fn)
