import os
from pathlib import Path

from eth_consensus_specs.utils.kzg import (
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
        "--g1-length",
        dest="g1_length",
        type=int,
        required=True,
        help='the length of G1 trusted setup',
    )
    parser.add_argument(
        "--g2-length",
        dest="g2_length",
        type=int,
        required=True,
        help='the length of G2 trusted setup',
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        dest="output_dir",
        required=True,
        help='the output directory',
    )
    args = parser.parse_args()

    dump_kzg_trusted_setup_files(args.secret, args.g1_length, args.g2_length, args.output_dir)
