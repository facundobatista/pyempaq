# Copyright 2021 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Tests for some main helpers."""

import pathlib
import sys
from unittest.mock import patch

import pytest

from pyempaq.main import get_pip, ExecutionError


@pytest.mark.parametrize("version", [
    r"pip 21.2.1 from c:\hostedtool\windows\python\3.8.10\x64\lib\site-packages\pip (python 3.8)",
    "pip 20.1.1 from /usr/lib/python3/dist-packages/pip (python 3.8)",
])
def test_get_pip_installed_useful(version):
    """An already installed pip is found."""
    with patch("pyempaq.main.logged_exec") as mock_exec:
        mock_exec.return_value = [version]
        useful_pip = get_pip()
    assert useful_pip == pathlib.Path("pip3")


@pytest.mark.skipif(sys.platform.startswith("win"), reason="venv.create not working in GA Windows")
def test_get_pip_failing_pip(tmp_path):
    """An already installed pip is failing."""
    with patch("pyempaq.main.logged_exec") as mock_exec:
        with patch("tempfile.mkdtemp") as mock_tempdir:
            mock_exec.side_effect = ExecutionError("pumba")
            mock_tempdir.return_value = tmp_path
            useful_pip = get_pip()
    # from inside a venv
    assert (
        useful_pip == tmp_path / "bin" / "pip3" or useful_pip == tmp_path / "Scripts" / "pip3.exe")
