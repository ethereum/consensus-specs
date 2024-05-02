from .phase0 import Phase0SpecBuilder
from .altair import AltairSpecBuilder
from .bellatrix import BellatrixSpecBuilder
from .capella import CapellaSpecBuilder
from .deneb import DenebSpecBuilder
from .electra import ElectraSpecBuilder
from .whisk import WhiskSpecBuilder
from .eip7594 import EIP7594SpecBuilder


spec_builders = {
    builder.fork: builder
    for builder in (
        Phase0SpecBuilder, AltairSpecBuilder, BellatrixSpecBuilder, CapellaSpecBuilder, DenebSpecBuilder,
        ElectraSpecBuilder, WhiskSpecBuilder, EIP7594SpecBuilder,
    )
}
