from setuptools import setup, find_packages


deps = {
    'gen_base': [
        "ruamel.yaml==0.15.87",
        "eth-utils==1.4.1",
    ],
}

deps['dev'] = (
    deps['gen_base']
)

install_requires = deps['gen_base']

setup(
    name='gen_helpers',
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=install_requires,
)
