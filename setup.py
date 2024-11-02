from setuptools import setup, find_packages

setup(
    name="vpm",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "typer>=0.9.0",
        "rich>=10.0.0",
        "shellingham>=1.5.0",
    ],
    entry_points={
        "console_scripts": [
            "vpm=vpm.cli:app",
        ],
    },
) 