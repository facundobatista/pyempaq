# Copyright 2021-2023 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Tests for some main helpers."""

import errno
import os
import pathlib
import socket
import sys
from unittest.mock import patch

import pytest

from pyempaq.main import get_pip, copy_project
from pyempaq.common import ExecutionError
from pyempaq.config_manager import DEFAULT_INCLUDE_LIST


# -- tests for get pip


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


# -- tests for copy project

# the default include/exclude structures, so all tests that work with the default are simpler
DEFAULT_INC_EXC = DEFAULT_INCLUDE_LIST, []


@pytest.fixture
def src(tmp_path):
    """Provide an already created source directory."""
    tmp = tmp_path / "src"
    tmp.mkdir()
    yield tmp


@pytest.fixture
def dest(tmp_path):
    """Provide a not yet created destination directory."""
    tmp = tmp_path / "dest"
    yield tmp


def test_copyproject_simple_structure(src, dest):
    """Copy a directory and a file."""
    (src / "foo").touch()
    (src / "bar").mkdir()
    (src / "bar" / "baz").touch()

    copy_project(src, dest, *DEFAULT_INC_EXC)

    foo = dest / "foo"
    assert foo.exists()
    assert foo.is_file()
    bar = dest / "bar"
    assert bar.exists()
    assert bar.is_dir()
    baz = dest / "bar" / "baz"
    assert baz.exists()
    assert baz.is_file()


def test_copyproject_content_and_metadata(src, dest):
    """Respect content and metadata."""
    src_file = (src / "foo")
    src_file.write_text("test content")
    src_file.chmod(0o775)
    src_dir = (src / "bar")
    src_dir.mkdir(mode=0o700)

    copy_project(src, dest, *DEFAULT_INC_EXC)

    dest_file = dest / "foo"
    assert dest_file.is_file()
    assert dest_file.read_text() == "test content"
    assert dest_file.stat().st_mode == src_file.stat().st_mode
    dest_dir = dest / "bar"
    assert dest_dir.is_dir()
    assert dest_dir.stat().st_mode == src_dir.stat().st_mode


def test_copyproject_hidden_default_ignored(src, dest):
    """Do not include hidden directories or files by default."""
    (src / ".foo").touch()
    (src / ".bar").mkdir()

    copy_project(src, dest, *DEFAULT_INC_EXC)

    assert list(dest.iterdir()) == []


def test_copyproject_hidden_included_if_specified(src, dest):
    """Do include hidden directories and files if specified."""
    (src / ".foo").touch()
    (src / ".bar").mkdir()

    include = ["./.*"]
    exclude = []
    copy_project(src, dest, include, exclude)

    assert set(dest.iterdir()) == {dest / ".foo", dest / ".bar"}


def test_copyproject_ignore_excluded_nodes(src, dest, logs):
    """Do not include an excluded file or directory."""
    (src / "foo_file").touch()
    (src / "foo_dir").mkdir()
    (src / "bar_file").touch()
    (src / "bar_dir").mkdir()

    include = DEFAULT_INCLUDE_LIST
    exclude = ["foo*"]
    copy_project(src, dest, include, exclude)

    assert set(dest.iterdir()) == {dest / "bar_file", dest / "bar_dir"}
    assert "Ignoring excluded node: 'foo_file'" in logs.debug
    assert "Ignoring excluded node: 'foo_dir'" in logs.debug


def test_copyproject_ignore_excluded_parent(src, dest, logs):
    """Do not include a node if the parent is excluded."""
    foo_dir = src / "foo_dir"
    foo_dir.mkdir()
    (foo_dir / "foo_file").touch()
    bar_dir = src / "bar_dir"
    bar_dir.mkdir()
    (bar_dir / "bar_file").touch()

    include = DEFAULT_INCLUDE_LIST
    exclude = ["foo_dir"]
    copy_project(src, dest, include, exclude)

    assert (dest / "bar_dir").exists()
    assert (dest / "bar_dir" / "bar_file").exists()
    assert "Ignoring excluded node: 'foo_dir'" in logs.debug
    assert "Ignoring node because excluded parent: 'foo_dir/foo_file'" in logs.debug


def test_copyproject_include_nothing(src, dest):
    """Support nothing being included."""
    (src / "foo").touch()

    include = []
    exclude = []
    copy_project(src, dest, include, exclude)

    assert list(dest.iterdir()) == []


def test_copyproject_deeptree(src, dest):
    """Sanity check for a deep tree."""
    # create this structure:
    # ├─ file1.txt
    # ├─ dir1
    # │  └─ secret1  (ignored!)
    # └─ dir2
    #    ├─ file2.txt
    #    ├─ secret2.txt  (ignored!)
    #    ├─ cache  (ignored!)
    #    │   └─ file3.txt
    #    └─ dir3
    file1 = src / "file1.txt"
    file1.touch()
    dir1 = src / "dir1"
    dir1.mkdir()
    secret1 = dir1 / "secret1"
    secret1.touch()
    dir2 = src / "dir2"
    dir2.mkdir()
    file2 = dir2 / "file2.txt"
    file2.touch()
    secret2 = dir2 / "secret2.txt"
    secret2.touch()
    cache = dir2 / "cache"
    cache.mkdir()
    file3 = cache / "file3.txt"
    file3.touch()
    dir3 = dir2 / "dir3"
    dir3.mkdir()

    include = DEFAULT_INCLUDE_LIST
    exclude = ["**/secret*", "dir2/cache"]
    copy_project(src, dest, include, exclude)

    assert (dest / "file1.txt").exists()
    assert (dest / "dir1").exists()
    assert not (dest / "dir1" / "secret1").exists()
    assert (dest / "dir2").exists()
    assert (dest / "dir2" / "file2.txt").exists()
    assert not (dest / "dir2" / "secret2.txt").exists()
    assert not (dest / "dir2" / "cache").exists()
    assert (dest / "dir2" / "dir3").exists()


def test_copyproject_no_link_permission(src, dest):
    """The platform does not allow hard links."""
    src_file = src / "foo"
    src_file.write_text("test content")
    src_file.chmod(0o775)

    with patch("os.link", side_effect=PermissionError("No you don't.")):
        copy_project(src, dest, *DEFAULT_INC_EXC)

    dest_file = dest / "foo"
    assert dest_file.is_file()
    assert dest_file.read_text() == "test content"
    assert dest_file.stat().st_mode == src_file.stat().st_mode


def test_copyproject_cross_device(src, dest):
    """Hard links cannot be done from one device to other."""
    src_file = src / "foo"
    src_file.write_text("test content")
    src_file.chmod(0o775)

    os_error = OSError(errno.EXDEV, os.strerror(errno.EXDEV))
    with patch("os.link", side_effect=os_error):
        copy_project(src, dest, *DEFAULT_INC_EXC)

    dest_file = dest / "foo"
    assert dest_file.is_file()
    assert dest_file.read_text() == "test content"
    assert dest_file.stat().st_mode == src_file.stat().st_mode


def test_copyproject_symlink_file(src, dest):
    """Respect a symlinked file."""
    real_file = src / "foo"
    real_file.touch()
    src_symlink = src / "bar"
    src_symlink.symlink_to(real_file)

    copy_project(src, dest, *DEFAULT_INC_EXC)

    dest_symlink = dest / "bar"
    assert dest_symlink.is_symlink()
    assert dest_symlink.resolve() == dest / "foo"
    real_link = os.readlink(dest_symlink)
    assert real_link == "foo"


def test_copyproject_symlink_dir(src, dest):
    """Respect a symlinked dir."""
    real_dir = src / "foodir"
    real_dir.mkdir()
    real_file = real_dir / "foofile"
    real_file.touch()
    src_symlink = src / "bar"
    src_symlink.symlink_to(real_dir)

    copy_project(src, dest, *DEFAULT_INC_EXC)

    dest_symlink = dest / "bar"
    assert dest_symlink.is_symlink()
    assert dest_symlink.resolve() == dest / "foodir"
    real_link = os.readlink(dest_symlink)
    assert real_link == "foodir"

    # the file inside the linked dir should exist
    assert (dest / "bar" / "foofile").exists()


def test_copyproject_symlink_deep(src, dest):
    """Sanity check for symbolic links from one deep dir to other."""
    real_dir_1 = src / "dir1"
    real_dir_1.mkdir()
    real_dir_2 = src / "dir2"
    real_dir_2.mkdir()
    real_file = real_dir_1 / "real_file"
    real_file.touch()
    src_symlink = real_dir_2 / "the_link"
    src_symlink.symlink_to(real_file)

    copy_project(src, dest, *DEFAULT_INC_EXC)

    dest_symlink = dest / "dir2" / "the_link"
    assert dest_symlink.is_symlink()
    assert dest_symlink.resolve() == dest / "dir1" / "real_file"
    real_link = os.readlink(dest_symlink)
    assert real_link == "../dir1/real_file"


def test_copyproject_symlink_outside_file(src, dest, tmp_path, logs):
    """Ignore a symlink pointing to outside the root directory, case for a file."""
    out_dir = tmp_path / "outside"
    out_dir.mkdir()
    out_file = out_dir / "secrets"
    out_file.touch()

    src_symlink = src / "foo"
    src_symlink.symlink_to(out_file)

    copy_project(src, dest, *DEFAULT_INC_EXC)

    assert not (dest / "foo").exists()
    expected = f"Ignoring symlink because targets outside the project: 'foo' -> {str(out_file)!r}"
    assert expected in logs.debug


def test_copyproject_symlink_outside_directory(src, dest, tmp_path, logs):
    """Ignore a symlink pointing to outside the root directory, case for a dir."""
    out_dir = tmp_path / "outside"
    out_dir.mkdir()

    src_symlink = src / "foo"
    src_symlink.symlink_to(out_dir)

    copy_project(src, dest, *DEFAULT_INC_EXC)

    assert not (dest / "foo").exists()
    expected = f"Ignoring symlink because targets outside the project: 'foo' -> {str(out_dir)!r}"
    assert expected in logs.debug


def test_copyproject_weird_filetype(src, dest, logs, monkeypatch):
    """Ignore whatever is not a regular file, symlink or dir."""
    # change into the source directory and just bind the socket there, otherwise
    # its path will be too long for MacOS (because of the temp dir path used)
    monkeypatch.chdir(src)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind("test-socket")

    copy_project(src, dest, *DEFAULT_INC_EXC)

    assert not (dest / "test-socket").exists()
    assert "Ignoring file because of type: 'test-socket'" in logs.debug


def test_copyproject_specific_file_inside_directory_existing(src, dest):
    """Include an existing specific file inside a dir."""
    basedir = src / "base"
    basedir.mkdir()
    thefile = basedir / "foo"
    thefile.touch()

    copy_project(src, dest, ["base/foo"], [])

    destbase = dest / "base"
    assert destbase.exists()
    destfile = destbase / "foo"
    assert destfile.exists()
    assert destfile.is_file()


def test_copyproject_specific_file_inside_directory_missing(src, dest, logs):
    """Include a missing specific file inside a dir."""
    copy_project(src, dest, ["missingdir/missingfile"], [])
    assert "Cannot find nodes for specified pattern: 'missingdir/missingfile'" in logs.error


def test_copyproject_specific_file_inside_directory_ignored(src, dest, logs):
    """Include an existing specific file inside an ignored dir."""
    basedir = src / "base"
    basedir.mkdir()
    thefile = basedir / "foo"
    thefile.touch()

    copy_project(src, dest, ["base/foo"], ["base"])
    assert "Ignoring excluded node: 'base'" in logs.debug
