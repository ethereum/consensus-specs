from .phase0 import Phase0SpecBuilder
from .altair import AltairSpecBuilder
from .bellatrix import BellatrixSpecBuilder
from .capella import CapellaSpecBuilder
from .deneb import DenebSpecBuilder
from .eip6110 import EIP6110SpecBuilder
from .eip7002 import EIP7002SpecBuilder
from .whisk import WhiskSpecBuilder
from .eip7594 import EIP7594SpecBuilder


spec_builders = {
    builder.fork: builder
    for builder in (
        Phase0SpecBuilder, AltairSpecBuilder, BellatrixSpecBuilder, CapellaSpecBuilder, DenebSpecBuilder,
        EIP6110SpecBuilder, EIP7002SpecBuilder, WhiskSpecBuilder, EIP7594SpecBuilder,
    )
}
