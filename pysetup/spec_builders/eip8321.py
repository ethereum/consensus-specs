from pysetup.constants import EIP8321

from .base import BaseSpecBuilder


class EIP8321SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8321

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from blake3 import blake3 as blake3_hash

from eth_consensus_specs.heze import {preset_name} as heze
"""

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "upgrade_to_heze",
        }
