from setuptools import setup, find_packages


deps = {
    'pyspec': [
        "eth-utils>=1.3.0,<2",
        "eth-typing>=2.1.0,<3.0.0",
        "pycryptodome==3.7.3",
        "py_ecc>=1.6.0",
    ],
    'test': [
        "pytest>=3.6,<3.7",
    ],
}

deps['dev'] = (
    deps['pyspec'] +
    deps['test']
)

install_requires = deps['pyspec']

setup(
    name='pyspec',
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=install_requires,
    extras_require=deps,
)
