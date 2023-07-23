from .base import BaseSpecBuilder
from ..constants import EIP6110


class EIP6110SpecBuilder(BaseSpecBuilder):
    fork: str = EIP6110

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.deneb import {preset_name} as deneb
'''
