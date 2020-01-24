from setuptools import setup, find_packages

setup(
    name='pyspec',
    packages=find_packages(),
    python_requires=">=3.8, <4",
    tests_require=["pytest"],
    install_requires=[
        "eth-utils>=1.3.0,<2",
        "eth-typing>=2.1.0,<3.0.0",
        "pycryptodome==3.9.4",
        "py_ecc==2.0.0",
        "dataclasses==0.6",
        "remerkleable==0.1.10",
    ]
)
