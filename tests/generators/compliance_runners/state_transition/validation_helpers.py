"""Shared helpers for semantic validation of generated vectors."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from eth_consensus_specs.utils import bls

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextmanager
def bls_enabled() -> Iterator[None]:
    """Temporarily enable BLS verification and restore its prior global state."""
    previous = bls.bls_active
    bls.bls_active = True
    try:
        yield
    finally:
        bls.bls_active = previous
