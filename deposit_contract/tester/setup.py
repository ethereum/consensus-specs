from distutils.core import setup

setup(
    name='deposit_contract_tester',
    packages=['deposit_contract'],
    package_dir={"": "."},
    tests_requires=[],
    install_requires=[]  # see requirements.txt file
)
