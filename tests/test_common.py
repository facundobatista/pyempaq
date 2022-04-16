# Copyright 2022 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Common functions module tests."""

import pytest

from pyempaq.common import find_venv_bin


def test_find_venv_bin_l(tmp_path):
    """Search and find the directory for the executable (linux-like env)."""
    l_dir = tmp_path / "bin"
    l_dir.mkdir()
    find_venv = find_venv_bin(tmp_path, "pip_foo")
    assert find_venv == tmp_path / "bin" / "pip_foo"


def test_find_venv_bin_w(tmp_path):
    """Search and find the directory for the executable (windows env)."""
    w_dir = tmp_path / "Scripts"
    w_dir.mkdir()
    find_venv = find_venv_bin(tmp_path, "pip_bar")
    assert find_venv == tmp_path / "Scripts" / "pip_bar.exe"


def test_find_venv_bin_no(tmp_path):
    """Can't find directory for the executable and raise RuntimeError."""
    with pytest.raises(RuntimeError):
        find_venv_bin(tmp_path, "pip_baz")
