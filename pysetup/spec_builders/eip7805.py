from .base import BaseSpecBuilder
from ..constants import EIP7805


class EIP7805SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7805

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.electra import {preset_name} as electra
'''
