import os
from pathlib import Path

from eth2spec.utils.kzg import (
    dump_kzg_roots_of_unity,
)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--g1-length",
        dest="g1_length",
        type=int,
        required=True,
        help='the length of G1 trusted setup',
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="output_dir",
        required=True,
        help='the output directory',
    )
    args = parser.parse_args()

    dump_kzg_roots_of_unity(args.g1_length, args.output_dir)
