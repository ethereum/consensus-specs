from typing import Dict

from .base import BaseSpecBuilder
from ..constants import EIP6800


class EIP6800SpecBuilder(BaseSpecBuilder):
    fork: str = EIP6800

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.deneb import {preset_name} as deneb
from eth2spec.utils.ssz.ssz_typing import Bytes31
'''
