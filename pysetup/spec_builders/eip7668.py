from .base import BaseSpecBuilder
from ..constants import EIP7668


class EIP7668SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7668

    @classmethod
    def imports(cls, preset_name: str):
        return super().imports(preset_name) + f'''
from eth2spec.capella import {preset_name} as capella
'''
