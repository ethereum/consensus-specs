from pysetup.constants import EIP7716

from .base import BaseSpecBuilder


class EIP7716SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7716

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.heze import {preset_name} as heze
"""

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "upgrade_to_heze",
        }
