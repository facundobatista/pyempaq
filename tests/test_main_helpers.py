# Copyright 2021 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Tests for some main helpers."""

import pathlib
import sys
from unittest.mock import patch

import pytest

from pyempaq.main import get_pip, prepare_metadata
from pyempaq.common import ExecutionError
from pyempaq.config_manager import load_config


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
