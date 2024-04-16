from .base import BaseSpecBuilder
from ..constants import ELECTRA


class ElectraSpecBuilder(BaseSpecBuilder):
    fork: str = ELECTRA

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.deneb import {preset_name} as deneb
'''
