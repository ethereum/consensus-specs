
import random
from eth2spec.test.helpers.constants import (
    EIP4844,
    MINIMAL,
)
from eth2spec.test.context import (
    with_phases,
    spec_state_test,
    with_presets,
)


def _create_blob(spec):
    rng = random.Random(5566)
    return spec.Blob([
        rng.randint(0, spec.BLS_MODULUS - 1)
        for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)
    ])


@with_phases([EIP4844])
@spec_state_test
@with_presets([MINIMAL])
def test_blob_to_kzg(spec, state):
    blob = _create_blob(spec)
    spec.blob_to_kzg(blob)
