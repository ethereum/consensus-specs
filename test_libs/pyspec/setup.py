from setuptools import setup, find_packages

setup(
    name='pyspec',
    packages=find_packages(),
    tests_require=["pytest"],
    install_requires=[
        "eth-utils>=1.3.0,<2",
        "eth-typing>=2.1.0,<3.0.0",
        "pycryptodome==3.7.3",
        "py_ecc==1.7.1",
        "ssz==0.1.0a10",
        "dataclasses==0.6",
    ]
)
