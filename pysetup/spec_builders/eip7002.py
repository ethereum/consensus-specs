from .base import BaseSpecBuilder
from ..constants import EIP7002


class EIP7002SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7002

    @classmethod
    def imports(cls, preset_name: str):
        return super().imports(preset_name) + f'''
from eth2spec.capella import {preset_name} as capella
'''
