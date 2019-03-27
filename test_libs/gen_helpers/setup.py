from distutils.core import setup

setup(
    name='gen_helpers',
    version='1.0',
    packages=['gen_base'],
    install_requires=['ruamel.yaml', 'eth-utils']
)
