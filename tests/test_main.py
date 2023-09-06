# Copyright 2021-2023 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Tests for main's pack and helpers."""

import errno
import os
import pathlib
import socket
import sys
import zipfile

import pytest
from logassert import Exact

from pyempaq.main import get_pip, copy_project, prepare_metadata, pack
from pyempaq.common import ExecutionError
from pyempaq.config_manager import DEFAULT_INCLUDE_LIST, load_config


# -- tests for pack

def _build_config(tmp_path, content):
    """Build, parse and return a config object."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(content)
    return load_config(config_file)


def test_pack_sanity(mocker, tmp_path, monkeypatch):
    """Sanity check of pack function.

    Note that comprehensive testing of packing is mostly done on integration testing.
    """
    # working directory
    work_dir = tmp_path / "worktemp"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)

    # fake packing temp dir
    pack_tmp_dir = tmp_path / "testtemp"
    pack_tmp_dir.mkdir()
    mocker.patch("tempfile.mkdtemp", return_value=str(pack_tmp_dir))

    # fake a project source to be packed
    project_src = tmp_path / "workingproject"
    project_src.mkdir()
    project_src_file_1 = project_src / "file1.txt"
    project_src_file_1.write_text("file1")
    project_src_script = project_src / "script.py"
    project_src_script.write_text("superpython")
    project_src_dir_1 = project_src / "subdir"
    project_src_dir_1.mkdir()
    project_src_file_2 = project_src_dir_1 / "file2.txt"
    project_src_file_2.write_text("file2")

    # the config
    config = _build_config(tmp_path, f"""
        name: testproject
        basedir: {project_src}
        exec:
            script: script.py
    """)

    # run
    pack(config)

    # check the tmp dir was cleaned
    assert not pack_tmp_dir.exists()

    # open the created zip file and assert content
    zf = zipfile.ZipFile(work_dir / "testproject.pyz")
    assert {name.split("/")[0] for name in zf.namelist()} == {
        'orig',  # the original project
        '__main__.py',  # the zip entry point
        'pyempaq',  # pyempaq's support for execution later
        'metadata.json',  # metadata for ^ to work
        'venv',  # dependencies also for ^
    }

    # original project data
    assert zf.read("orig/file1.txt") == b"file1"
    assert zf.read("orig/subdir/file2.txt") == b"file2"
    assert zf.read("orig/script.py") == b"superpython"

    # pyempaq's support
    pyempaq_src = pathlib.Path(__file__).parent.parent / "pyempaq"
    assert zf.read("__main__.py") == (pyempaq_src / "unpacker.py").read_bytes()
    assert zf.read("pyempaq/common.py") == (pyempaq_src / "common.py").read_bytes()


# -- tests for get pip


@pytest.mark.parametrize("version", [
    r"pip 21.2.1 from c:\hostedtool\windows\python\3.8.10\x64\lib\site-packages\pip (python 3.8)",
    "pip 20.1.1 from /usr/lib/python3/dist-packages/pip (python 3.8)",
])
def test_get_pip_installed_useful(version, mocker):
    """An already installed pip is found."""
    mocker.patch("pyempaq.main.logged_exec", return_value=[version])
    useful_pip = get_pip()
    assert useful_pip == pathlib.Path("pip3")


@pytest.mark.skipif(sys.platform.startswith("win"), reason="venv.create not working in GA Windows")
def test_get_pip_failing_pip(tmp_path, mocker):
    """An already installed pip is failing.

    This test takes a while because it really creates a virtualenv.
    """
    mocker.patch("pyempaq.main.logged_exec", side_effect=ExecutionError("pumba"))
    mocker.patch("tempfile.mkdtemp", return_value=tmp_path)
    useful_pip = get_pip()

    # from inside a venv
    assert useful_pip in (tmp_path / "bin" / "pip3", tmp_path / "Scripts" / "pip3.exe")


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
    excluded = os.path.join("foo_dir", "foo_file")
    assert Exact(f"Ignoring node because excluded parent: {excluded!r}") in logs.debug


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


def test_copyproject_no_link_permission(src, dest, mocker):
    """The platform does not allow hard links."""
    src_file = src / "foo"
    src_file.write_text("test content")
    src_file.chmod(0o775)

    mocker.patch("os.link", side_effect=PermissionError("No you don't."))
    copy_project(src, dest, *DEFAULT_INC_EXC)

    dest_file = dest / "foo"
    assert dest_file.is_file()
    assert dest_file.read_text() == "test content"
    assert dest_file.stat().st_mode == src_file.stat().st_mode


def test_copyproject_cross_device(src, dest, mocker):
    """Hard links cannot be done from one device to other."""
    src_file = src / "foo"
    src_file.write_text("test content")
    src_file.chmod(0o775)

    os_error = OSError(errno.EXDEV, os.strerror(errno.EXDEV))
    mocker.patch("os.link", side_effect=os_error)
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
    assert real_link == os.path.join("..", "dir1", "real_file")


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
    assert Exact(expected) in logs.debug


def test_copyproject_symlink_outside_directory(src, dest, tmp_path, logs):
    """Ignore a symlink pointing to outside the root directory, case for a dir."""
    out_dir = tmp_path / "outside"
    out_dir.mkdir()

    src_symlink = src / "foo"
    src_symlink.symlink_to(out_dir)

    copy_project(src, dest, *DEFAULT_INC_EXC)

    assert not (dest / "foo").exists()
    expected = f"Ignoring symlink because targets outside the project: 'foo' -> {str(out_dir)!r}"
    assert Exact(expected) in logs.debug


@pytest.mark.skipif(sys.platform == "win32", reason="Unix sockets are not possible in Windows")
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
    excluded = os.path.join("base", "foo")
    assert Exact(f"Ignoring node because excluded parent: {excluded!r}") in logs.debug


# -- tests for metadata generation


def test_metadata_base_exec_script(tmp_path):
    """Simple basic metadata for exec script."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            script: script.py
    """)
    (tmp_path / "script.py").touch()
    config = load_config(config_file)

    metadata = prepare_metadata(tmp_path, config)
    assert metadata == {
        "requirement_files": [],
        "project_name": "testproject",
        "exec_default_args": [],
        "exec_style": "script",
        "exec_value": "script.py",
        "unpack_restrictions": {},
    }


def test_metadata_base_exec_module(tmp_path):
    """Simple basic metadata for exec module."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            module: foobar
    """)
    (tmp_path / "foobar").mkdir()
    config = load_config(config_file)

    metadata = prepare_metadata(tmp_path, config)
    assert metadata == {
        "requirement_files": [],
        "project_name": "testproject",
        "exec_default_args": [],
        "exec_style": "module",
        "exec_value": "foobar",
        "unpack_restrictions": {},
    }


def test_metadata_base_exec_entrypoint(tmp_path):
    """Simple basic metadata for exec entrypoint."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: [foo, bar]
    """)
    config = load_config(config_file)

    metadata = prepare_metadata(tmp_path, config)
    assert metadata == {
        "requirement_files": [],
        "project_name": "testproject",
        "exec_default_args": [],
        "exec_style": "entrypoint",
        "exec_value": "['foo', 'bar']",
        "unpack_restrictions": {},
    }


def test_metadata_requirements(tmp_path):
    """Metadata with requirement files."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: [foo, bar]
        requirements:
            - reqs1.txt
            - reqs2.txt
    """)
    (tmp_path / "reqs1.txt").touch()
    (tmp_path / "reqs2.txt").touch()
    config = load_config(config_file)

    metadata = prepare_metadata(tmp_path, config)
    assert metadata["requirement_files"] == ["reqs1.txt", "reqs2.txt"]


def test_metadata_dependencies(tmp_path):
    """Metadata with extra dependencies."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: [foo, bar]
        dependencies:
            - abc
            - def < 5.2
    """)
    config = load_config(config_file)

    metadata = prepare_metadata(tmp_path, config)
    (extra_req,) = metadata["requirement_files"]
    assert (tmp_path / extra_req).read_text() == "abc\ndef < 5.2\n"


def test_metadata_requirements_and_dependencies(tmp_path):
    """Metadata with both requirement files and dependencies."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: [foo, bar]
        requirements:
            - reqs.txt
        dependencies:
            - extradep == 2.0
    """)
    (tmp_path / "reqs.txt").touch()
    config = load_config(config_file)

    metadata = prepare_metadata(tmp_path, config)
    user_req, extra_req = metadata["requirement_files"]
    assert user_req == "reqs.txt"
    assert (tmp_path / extra_req).read_text() == "extradep == 2.0\n"


def test_metadata_unpack_restrictions(tmp_path):
    """Metadata with unpack restrictions."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: [foo, bar]
        unpack-restrictions:
            minimum-python-version: "3.9"
    """)
    config = load_config(config_file)

    metadata = prepare_metadata(tmp_path, config)
    assert metadata["unpack_restrictions"]["minimum_python_version"] == "3.9"
