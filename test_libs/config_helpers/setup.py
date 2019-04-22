from distutils.core import setup


deps = {
    'config_helpers': [
        "ruamel.yaml==0.15.87",
    ],
}

deps['dev'] = (
    deps['config_helpers']
)

setup(
    name='config_helpers',
    packages=['preset_loader'],
    install_requires=deps['config_helpers']
)
