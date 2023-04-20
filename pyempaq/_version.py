# Copyright 2023 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Holder of the PyEmpaq version number."""

# these two will be exported at `pyempaq` module level by __init__.py; also VERSION will
# be parsed by setup.py without needing to import the module (at moments when the
# version is needed but the infrastructure is not in place yet)
VERSION = (0, 3, 0)
__version__ = '.'.join([str(x) for x in VERSION])
