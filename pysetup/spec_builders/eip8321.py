from pysetup.constants import EIP8321

from .base import BaseSpecBuilder


class EIP8321SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8321

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.utils.hash_function import blake3

from eth_consensus_specs.heze import {preset_name} as heze
"""
