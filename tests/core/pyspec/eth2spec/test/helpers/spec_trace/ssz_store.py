"""
SSZ object storage with content-addressed deduplication.

This module provides efficient storage for SSZ objects used in trace generation.
"""

from __future__ import annotations

from pathlib import Path

from eth2spec.utils.ssz.ssz_impl import hash_tree_root, serialize
from eth2spec.utils.ssz.ssz_typing import View

__all__ = ["SSZObjectStore"]


class SSZObjectStore:
    """
    Manages storage of SSZ objects using content-addressed storage.

    Objects are stored once and referenced by their hash_tree_root, eliminating
    duplication across multiple test traces.

    Attributes:
        output_dir: Directory where SSZ objects are stored
        _stored_roots: Set of already-stored object roots (for deduplication)
    """

    def __init__(self, output_dir: Path) -> None:
        """
        Initialize the SSZ object store.

        Args:
            output_dir: Path to directory for storing SSZ objects
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._stored_roots: set[str] = set()

    def store_object(self, obj: View) -> str:
        """
        Store an SSZ object and return its root hash.

        If an object with the same hash already exists, it won't be stored again
        (content-addressed deduplication).

        Args:
            obj: SSZ View object to store

        Returns:
            Hex-encoded hash tree root of the object
        """
        root = hash_tree_root(obj)
        root_hex = root.hex()

        if root_hex not in self._stored_roots:
            filename = f"{root_hex}.ssz_snappy"
            filepath = self.output_dir / filename

            # Serialize (TODO: Add snappy compression in future PR)
            ssz_bytes = serialize(obj)
            filepath.write_bytes(ssz_bytes)

            self._stored_roots.add(root_hex)

        return root_hex

    def get_reference(self, obj: View) -> dict[str, str]:
        """
        Get a reference dict for use in trace YAML.

        Args:
            obj: SSZ View object to reference

        Returns:
            Dictionary with 'ssz_file' key pointing to the stored file
        """
        root = self.store_object(obj)
        return {"ssz_file": f"{root}.ssz_snappy"}
