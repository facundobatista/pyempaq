# Copyright 2021 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Tests for some main helpers."""

import pathlib
from unittest.mock import patch

from pyempaq.main import get_pip, ExecutionError


def test_get_pip_installed_useful():
    """An already installed pip is found."""
    pip_version = "pip 20.1.1 from /usr/lib/python3/dist-packages/pip (python 3.8)"
    with patch("pyempaq.main.logged_exec") as mock_exec:
        mock_exec.return_value = [pip_version]
        useful_pip = get_pip()
    assert useful_pip == pathlib.Path("pip")


def test_get_pip_installed_python2(tmp_path):
    """An already installed pip is found, but it's an old one."""
    pip_version = "pip 9.0.1 from /usr/lib/python2.7/dist-packages (python 2.7)"
    with patch("pyempaq.main.logged_exec") as mock_exec:
        with patch("tempfile.mkdtemp") as mock_tempdir:
            mock_exec.return_value = [pip_version]
            mock_tempdir.return_value = str(tmp_path)
            useful_pip = get_pip()
    # from inside a venv
    assert useful_pip == tmp_path / "bin" / "pip" or useful_pip == tmp_path / "Scripts" / "pip.exe"


def test_get_pip_failing_pip(tmp_path):
    """An already installed pip is failing."""
    with patch("pyempaq.main.logged_exec") as mock_exec:
        with patch("tempfile.mkdtemp") as mock_tempdir:
            mock_exec.side_effect = ExecutionError("pumba")
            mock_tempdir.return_value = tmp_path
            useful_pip = get_pip()
    # from inside a venv
    assert useful_pip == tmp_path / "bin" / "pip" or useful_pip == tmp_path / "Scripts" / "pip.exe"
