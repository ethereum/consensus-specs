from ..constants import EIP7928
from .base import BaseSpecBuilder


class EIP7928SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7928

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.fulu import {preset_name} as fulu
"""
