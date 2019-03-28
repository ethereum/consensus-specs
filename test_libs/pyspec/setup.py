from distutils.core import setup

setup(
    name='pyspec',
    version='1.0',
    packages=['eth2.debug', 'eth2.phase0', 'eth2.utils'],
    install_requires=[
        "eth-utils>=1.3.0,<2",
        "eth-typing>=2.1.0,<3.0.0",
        "pycryptodome==3.7.3",
        "py_ecc>=1.6.0",
    ]
)
