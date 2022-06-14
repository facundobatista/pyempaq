# Copyright 2022 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Common functions module tests."""

from logassert import Exact
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


def test_logged_exec(logs):
    """Execute a command, redirecting the output to the log. Everything OK."""
    logged_exec(['echo', 'test'])

    assert Exact("Executing external command: ['echo', 'test']") in logs.debug


def test_logged_exec_error(fp):
    """Execute a command, raises an error."""
    with pytest.raises(Exception) as e:
        logged_exec(["pip_baz"])

    assert str(e.value)[:32] == "Command ['pip_baz'] crashed with"


def test_logged_exec_retcode(fp):
    """Execute a command and ended with some return code."""
    fp.register(['pip_foo'], returncode=1800)

    with pytest.raises(Exception) as e:
        logged_exec(['pip_foo'])

    assert str(e.value) == "Command ['pip_foo'] ended with retcode 1800"
