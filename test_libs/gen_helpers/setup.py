from distutils.core import setup

setup(
    name='gen_helpers',
    packages=['gen_base'],
    install_requires=[
        "ruamel.yaml==0.15.87",
        "eth-utils==1.4.1"
    ]
)
