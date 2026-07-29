from pysetup.constants import EIP8198

from .base import BaseSpecBuilder


class EIP8198SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8198

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.heze import {preset_name} as heze
"""

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "on_tick_per_slot",
        }
