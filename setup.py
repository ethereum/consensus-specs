from setuptools import find_packages, setup

# Minimal setup.py for package configuration.
# The spec generation logic has been moved to pysetup/generate_specs.py
# and is now called explicitly by the Makefile before package installation.
#
# To generate specs, run: make _pyspec
# Or directly: python -m pysetup.generate_specs --all-forks

setup(
    include_package_data=False,
    package_data={
        "configs": ["*.yaml"],
        "eth_consensus_specs": ["VERSION.txt"],
        "presets": ["**/*.yaml", "**/*.json"],
        "specs": ["**/*.md"],
        "sync": ["optimistic.md"],
    },
    package_dir={
        "configs": "configs",
        "eth_consensus_specs": "tests/core/pyspec/eth_consensus_specs",
        "presets": "presets",
        "specs": "specs",
        "sync": "sync",
    },
    packages=find_packages(where="tests/core/pyspec") + ["configs", "presets", "specs", "sync"],
    py_modules=["eth_consensus_specs"],
)
