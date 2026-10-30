from pysetup.constants import EIP8450

from .base import BaseSpecBuilder


class EIP8450SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8450

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.heze import {preset_name} as heze
from eth_consensus_specs.utils import xmss
"""

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "upgrade_to_heze",
        }
