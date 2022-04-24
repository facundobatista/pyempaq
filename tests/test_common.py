# Copyright 2022 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Common functions module tests."""

import logging
import pytest

from pyempaq.common import logged_exec, find_venv_bin


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


def test_logged_exec(caplog):
    """Execute a command, redirecting the output to the log. Everything OK."""
    with caplog.at_level(logging.DEBUG):
        stdout = logged_exec(['echo', 'test'])

    assert stdout == ['test']
    assert "Executing external command: ['echo', 'test']" in caplog.text


def test_logged_exec_error():
    """Execute a command, raises an error."""
    with pytest.raises(Exception) as e:
        logged_exec(["pip_bar", "pip_baz"])

    assert "Command ['pip_bar', 'pip_baz'] crashed with " in str(e.value)


def test_logged_exec_wait():
    """Execute a command and ended with some return code."""
    with pytest.raises(Exception) as e:
        logged_exec(['dir', '$?'])
    assert str(e.value) == "Command ['dir', '$?'] ended with retcode 2"
