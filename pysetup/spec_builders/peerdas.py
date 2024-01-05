from typing import Dict

from .base import BaseSpecBuilder
from ..constants import PEERDAS


class PeerDASSpecBuilder(BaseSpecBuilder):
    fork: str = PEERDAS

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.deneb import {preset_name} as deneb
'''
