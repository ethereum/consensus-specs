from pysetup.constants import EIP8148

from .base import BaseSpecBuilder


class EIP8148SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8148

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.heze import {preset_name} as heze
"""
