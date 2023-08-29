from setuptools import find_packages, setup

setup(
    name="antarcticmap",
    packages=find_packages(exclude=["antarcticmap_tests"]),
    install_requires=[
        "dagster",
        "dagster-cloud",
        "gdal==3.6.2",
        "rasterio",
        "matplotlib",
    ],
    extras_require={"dev": ["dagster-webserver", "pytest"]},
)
