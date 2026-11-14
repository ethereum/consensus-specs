"""Readers for serialized test-vector files."""

from pathlib import Path

import snappy
from ruamel.yaml import YAML


def read_yaml(path):
    with Path(path).open() as stream:
        return YAML(typ="safe").load(stream)


def read_meta(path):
    return (read_yaml(path) or {}) if Path(path).exists() else {}


def read_ssz_snappy(path):
    return snappy.decompress(Path(path).read_bytes())
