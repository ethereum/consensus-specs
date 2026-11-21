from pysetup.constants import EIP8483

from .base import BaseSpecBuilder


class EIP8483SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8483

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.heze import {preset_name} as heze
from eth_consensus_specs.utils.ssz.bytes import Bytes64
"""

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "upgrade_to_heze",
        }
