from setuptools import setup, find_packages


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
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=install_requires,
)
