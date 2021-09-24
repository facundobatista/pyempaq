#!/usr/bin/env python3

# Copyright 2021 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Setup script for PyEmpaq."""

from setuptools import setup

with open("requirements.txt", "rt") as fh:
    install_requires = [x.strip() for x in fh]

setup(
    name="pyempaq",
    version="0.2",
    author="Facundo Batista",
    author_email="facundo@taniquetil.com.ar",
    description="A Python packer to run anywhwere any project with any virtualenv dependencies.",
    long_description=open("README.md", "rt", encoding="utf8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/facundobatista/pyempaq",
    license="GPL-v3",
    packages=["pyempaq"],
    classifiers=[
        "Environment :: Console",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: System :: Archiving :: Packaging",
        "Topic :: System :: Software Distribution",
    ],
    entry_points={
        "console_scripts": ["pyempaq = pyempaq.main:main"],
    },
    install_requires=install_requires,
    python_requires=">=3.5",
)
