from setuptools import find_packages, setup

setup(
    name="spotify-snapshot",
    version="0.0.1",
    packages=find_packages(),
    entry_points={
        "console_scripts": ["spotify-snapshot=spotify_snapshot.__main__:main"],
    },
)
