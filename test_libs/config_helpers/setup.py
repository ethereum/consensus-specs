from distutils.core import setup


deps = {
    'preset_loader': [
        "ruamel.yaml==0.15.87",
    ],
}

deps['dev'] = (
    deps['preset_loader']
)

install_requires = deps['preset_loader']

setup(
    name='config_helpers',
    packages=['preset_loader'],
    install_requires=install_requires,
)
