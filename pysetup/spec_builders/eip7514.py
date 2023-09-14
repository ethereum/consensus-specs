from .base import BaseSpecBuilder
from ..constants import EIP7514


class EIP7514SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7514

    @classmethod
    def imports(cls, preset_name: str):
        return super().imports(preset_name) + f'''
from eth2spec.capella import {preset_name} as capella
'''
