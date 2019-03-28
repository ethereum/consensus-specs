from setuptools import setup, find_packages

setup(
    name='pyspec',
    packages=find_packages(),
    install_requires=[
        "eth-utils>=1.3.0,<2",
        "eth-typing>=2.1.0,<3.0.0",
        "pycryptodome==3.7.3",
        "py_ecc>=1.6.0",
    ]
)
