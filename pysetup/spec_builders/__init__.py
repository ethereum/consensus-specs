from .phase0 import Phase0SpecBuilder
from .altair import AltairSpecBuilder
from .bellatrix import BellatrixSpecBuilder
from .capella import CapellaSpecBuilder
from .deneb import DenebSpecBuilder
from .electra import ElectraSpecBuilder
from .fulu import FuluSpecBuilder
from .whisk import WhiskSpecBuilder
from .eip6800 import EIP6800SpecBuilder
from .eip7732 import EIP7732SpecBuilder


spec_builders = {
    builder.fork: builder
    for builder in (
        Phase0SpecBuilder, AltairSpecBuilder, BellatrixSpecBuilder, CapellaSpecBuilder, DenebSpecBuilder,
        ElectraSpecBuilder, FuluSpecBuilder, WhiskSpecBuilder, EIP6800SpecBuilder, EIP7732SpecBuilder,
    )
}
