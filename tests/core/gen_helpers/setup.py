from distutils.core import setup

setup(
    name='gen_helpers',
    packages=['gen_base', 'gen_from_tests'],
    install_requires=[
        "ruamel.yaml==0.16.5",
        "eth-utils==1.6.0"
    ]
)
