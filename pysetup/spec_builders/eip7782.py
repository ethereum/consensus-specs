from ..constants import EIP7782
from .base import BaseSpecBuilder


class EIP7782SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7782

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth2spec.fulu import {preset_name} as fulu
"""
