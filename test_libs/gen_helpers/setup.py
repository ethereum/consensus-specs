from distutils.core import setup

setup(
    name='gen_helpers',
    packages=['gen_base'],
    install_requires=[
        "ruamel.yaml==0.15.96",
        "eth-utils==1.6.0"
    ]
)
