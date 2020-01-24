from distutils.core import setup

setup(
    name='deposit_contract_compiler',
    packages=['deposit_contract'],
    package_dir={"": "."},
    python_requires="3.7",  # pinned vyper compiler stops working after 3.7. See vyper issue 1835.
    tests_requires=["pytest==3.6.1"],
    install_requires=[],  # see requirements.txt file
)
