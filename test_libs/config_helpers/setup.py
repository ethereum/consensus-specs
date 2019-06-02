from distutils.core import setup

setup(
    name='config_helpers',
    packages=['preset_loader'],
    install_requires=[
        "ruamel.yaml==0.15.96"
    ]
)
