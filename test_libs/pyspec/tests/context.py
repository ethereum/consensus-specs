
from eth2spec.phase0 import spec
from tests.utils import with_args

from .helpers import (
    create_genesis_state,
)

# Provides a genesis state as first argument to the function decorated with this
with_state = with_args(lambda: [create_genesis_state(spec.SLOTS_PER_EPOCH * 8, list())])
