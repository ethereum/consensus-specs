"""
Helper functions to get SSZ objects from files and output them.
"""

from pathlib import Path
from typing import TypeVar

import snappy
from ruamel.yaml import YAML

from eth_consensus_specs.debug.encode import encode
from eth_consensus_specs.utils.ssz.ssz_impl import deserialize

SSZObject = TypeVar("SSZObject")


def get_ssz_object_from_ssz_encoded(file_path: Path, typ: SSZObject) -> SSZObject:
    """
    Get the SSZObject from an SSZ-encoded file.

    Automatically detects whether the file is snappy-compressed based on the file extension:
    - .ssz_snappy: snappy-compressed
    - .ssz: uncompressed

    Args:
        file_path: Path to the SSZ file (.ssz or .ssz_snappy)
        typ: The SSZ type to deserialize into

    Returns:
        The deserialized SSZ object

    Raises:
        ValueError: If the file extension is not .ssz or .ssz_snappy
    """
    with open(file_path, "rb") as f:
        data = f.read()

    # Determine if snappy-compressed based on file extension
    if file_path.suffix == ".ssz_snappy" or file_path.name.endswith(".ssz_snappy"):
        data = snappy.decompress(data)
    elif file_path.suffix == ".ssz":
        pass  # No decompression needed
    else:
        raise ValueError(
            f"Unsupported file extension: {file_path.suffix}. Expected .ssz or .ssz_snappy"
        )

    return deserialize(typ, data)


def output_ssz_to_file(
    output_path: Path, obj: SSZObject, include_hash_tree_roots: bool = False
) -> None:
    """
    Output an SSZ object to a YAML file.

    Args:
        output_path: Path where to save the YAML file
        obj: The SSZ object to encode
        include_hash_tree_roots: Whether to include hash tree roots in the output
    """
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=2, offset=0)
    yaml.width = 4096

    encoded = encode(obj, include_hash_tree_roots)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(encoded, f)
