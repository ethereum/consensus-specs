from .phase0 import Phase0SpecBuilder
from .altair import AltairSpecBuilder
from .bellatrix import BellatrixSpecBuilder
from .capella import CapellaSpecBuilder
from .deneb import DenebSpecBuilder
from .electra import ElectraSpecBuilder
from .fulu import FuluSpecBuilder
from .eip6800 import EIP6800SpecBuilder
from .eip7441 import EIP7441SpecBuilder
from .eip7732 import EIP7732SpecBuilder
from .eip7805 import EIP7805SpecBuilder


spec_builders = {
    builder.fork: builder
    for builder in (
        Phase0SpecBuilder, AltairSpecBuilder, BellatrixSpecBuilder, CapellaSpecBuilder, DenebSpecBuilder,
        ElectraSpecBuilder, FuluSpecBuilder, EIP6800SpecBuilder, EIP7441SpecBuilder, EIP7732SpecBuilder,
        EIP7805SpecBuilder,
    )
}
