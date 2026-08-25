from pysetup.constants import EIP8205

from .base import BaseSpecBuilder


class EIP8205SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8205

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.heze import {preset_name} as heze
"""
