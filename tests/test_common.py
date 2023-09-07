# Copyright 2022-2023 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Common functions module tests."""

import hashlib

from logassert import Exact
import pytest

from pyempaq.common import logged_exec, find_venv_bin, get_file_hexdigest, get_disknode_hexdigest


# -- tests for find venv

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


# -- tests for logged exec

def test_logged_exec(logs):
    """Execute a command, redirecting the output to the log. Everything OK."""
    stdout = logged_exec(['echo', 'test', '123'])

    assert stdout == ['test 123']
    assert Exact("Executing external command: ['echo', 'test', '123']") in logs.debug


def test_logged_exec_error(fake_process):
    """Execute a command, raises an error."""
    with pytest.raises(Exception) as e:
        logged_exec(["pip_baz"])

    assert str(e.value)[:32] == "Command ['pip_baz'] crashed with"


def test_logged_exec_retcode(fake_process):
    """Execute a command and ended with some return code."""
    fake_process.register(['pip_foo'], returncode=1800)

    with pytest.raises(Exception) as e:
        logged_exec(['pip_foo'])

    assert str(e.value) == "Command ['pip_foo'] ended with retcode 1800"


# -- tests for file hexdigest

def test_filedigest(tmp_path):
    tempfile = tmp_path / "test"
    content = b"123" * 500_00
    tempfile.write_bytes(content)
    should_digest = hashlib.sha256(content).hexdigest()

    assert get_file_hexdigest(tempfile) == should_digest


def test_nodedigest_file(tmp_path):
    tempfile = tmp_path / "test"
    content = b"123" * 50
    tempfile.write_bytes(content)
    should_digest = hashlib.sha256(content).hexdigest()

    assert get_disknode_hexdigest(tempfile) == should_digest


def test_nodedigest_simpledir(tmp_path):
    tempdir = tmp_path / "somedir"
    tempdir.mkdir()

    tempfile = tempdir / "test"
    content = b"123" * 50
    tempfile.write_bytes(content)
    should_digest = hashlib.sha256(content).hexdigest()

    assert get_disknode_hexdigest(tempdir) == should_digest


def test_nodedigest_complexdir(tmp_path):
    tempdir = tmp_path / "somedir"
    tempdir.mkdir()

    tempfile1 = tempdir / "aaa"
    content1 = b"123" * 50
    tempfile1.write_bytes(content1)

    tempfile2 = tempdir / "hhh"
    content2 = b"3j2" * 50
    tempfile2.write_bytes(content2)

    tempsubdir = tempdir / "fff"
    tempsubdir.mkdir()
    tempfile3 = tempsubdir / "zzz"
    content3 = b"o2d" * 50
    tempfile3.write_bytes(content3)

    tempfile4 = tempsubdir / "yyy"
    content4 = b"axi" * 50
    tempfile4.write_bytes(content4)

    tempsubdir = tempdir / "nnn"
    tempsubdir.mkdir()
    tempfile5 = tempsubdir / "aaa"
    content5 = b";-d" * 50
    tempfile5.write_bytes(content5)

    # order is:
    #  1. aaa
    #  4. fff/yyy
    #  3. fff/zzz
    #  2. hhh
    #  5. nnn/aaa
    full_content = content1 + content4 + content3 + content2 + content5
    should_digest = hashlib.sha256(full_content).hexdigest()

    assert get_disknode_hexdigest(tempdir) == should_digest
