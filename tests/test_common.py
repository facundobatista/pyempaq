# Copyright 2022 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Common functions module tests."""

from pathlib import Path
import shutil
import tempfile

from pyempaq.common import find_venv_bin


def test_find_venv_bin():
    """Search and find the directory for the executable."""
    # temporary test directory
    tmpdir = Path(tempfile.mkdtemp())

    # linux-like enviroment
    l_dir = tmpdir / "bin"
    l_dir.mkdir()
    find_venv = find_venv_bin(tmpdir, "pip_foo")
    assert find_venv == tmpdir / "bin" / "pip_foo"
    shutil.rmtree(l_dir)  # for ignore linux env

    # windows enviroment
    w_dir = tmpdir / "Scripts"
    w_dir.mkdir()
    find_venv = find_venv_bin(tmpdir, "pip_foo")
    assert find_venv == tmpdir / "Scripts" / "pip_foo.exe"
