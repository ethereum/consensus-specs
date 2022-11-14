import os
from pathlib import Path

from eth2spec.utils.kzg import (
    dump_kzg_trusted_setup_files,
)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--secret",
        dest="secret",
        type=int,
        required=True,
        help='the secret of trusted setup',
    )
    parser.add_argument(
        "--length",
        dest="length",
        type=int,
        required=True,
        help='the length of trusted setup',
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="output_dir",
        required=True,
        help='the output directory',
    )
    args = parser.parse_args()

    dump_kzg_trusted_setup_files(args.secret, args.length, args.output_dir)
