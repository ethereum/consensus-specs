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

    @classmethod
    def hardcoded_custom_type_dep_constants(cls, spec_object) -> Dict[str, str]:
        return {
            'FIELD_ELEMENTS_PER_CELL': spec_object.preset_vars['FIELD_ELEMENTS_PER_CELL'].value,
        }
