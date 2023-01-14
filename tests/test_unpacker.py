# Copyright 2021-2023 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Unpacker tests."""

import zipfile
from pathlib import Path
from unittest.mock import patch

from pyempaq.unpacker import build_command, run_command, setup_project_directory


# --- tests for build_command


def test_buildcommand_script_default_empty():
    """Build a command in "script" mode."""
    metadata = {
        "exec_style": "script",
        "exec_value": "mystuff.py",
        "exec_default_args": [],
    }
    cmd = build_command("python.exe", metadata, [])
    assert cmd == ["python.exe", "mystuff.py"]


def test_buildcommand_module_default_empty():
    """Build a command in "module" mode."""
    metadata = {
        "exec_style": "module",
        "exec_value": "mymodule",
        "exec_default_args": [],
    }
    cmd = build_command("python.exe", metadata, [])
    assert cmd == ["python.exe", "-m", "mymodule"]


def test_buildcommand_entrypoint_default_empty():
    """Build a command in "entrypoint" mode."""
    metadata = {
        "exec_style": "entrypoint",
        "exec_value": ["whatever", "you", "want"],
        "exec_default_args": [],
    }
    cmd = build_command("python.exe", metadata, [])
    assert cmd == ["python.exe", "whatever", "you", "want"]


def test_buildcommand_script_default_nonempty():
    """Build a command with default args."""
    metadata = {
        "exec_style": "script",
        "exec_value": "mystuff.py",
        "exec_default_args": ["--foo", "3"],
    }
    cmd = build_command("python.exe", metadata, [])
    assert cmd == ["python.exe", "mystuff.py", "--foo", "3"]


def test_buildcommand_script_sysargs():
    """Build a command with user passed args."""
    metadata = {
        "exec_style": "script",
        "exec_value": "mystuff.py",
        "exec_default_args": ["--foo", "3"],
    }
    cmd = build_command("python.exe", metadata, ["--bar"])
    assert cmd == ["python.exe", "mystuff.py", "--bar"]


# --- tests for run_command


def test_runcommand_with_env_path(monkeypatch):
    """Run a command with a PATH in the env."""
    cmd = ["foo", "bar"]
    monkeypatch.setenv("TEST_PYEMPAQ", "123")
    monkeypatch.setenv("PATH", "previous-path")

    with patch("subprocess.run") as run_mock:
        run_command(Path("test-venv-dir"), cmd)

    (call1,) = run_mock.call_args_list
    assert call1[0] == (cmd,)
    passed_env = call1[1]["env"]
    assert passed_env["TEST_PYEMPAQ"] == "123"
    assert passed_env["PATH"] == "previous-path:test-venv-dir"


def test_runcommand_no_env_path(monkeypatch):
    """Run a command without a PATH in the env."""
    cmd = ["foo", "bar"]
    monkeypatch.setenv("TEST_PYEMPAQ", "123")
    monkeypatch.delenv("PATH")

    with patch("subprocess.run") as run_mock:
        run_command(Path("test-venv-dir"), cmd)

    (call1,) = run_mock.call_args_list
    assert call1[0] == (cmd,)
    passed_env = call1[1]["env"]
    assert passed_env["TEST_PYEMPAQ"] == "123"
    assert passed_env["PATH"] == "test-venv-dir"


# --- tests for the project directory setup


@patch("pyempaq.unpacker.log")
def test_projectdir_simple(mocked_log, tmp_path):
    """Project directory without special requirements."""
    # fake a compressed project
    compressed_project = tmp_path / "project.zip"
    with zipfile.ZipFile(str(compressed_project), "w") as zf:  #str?
        zf.writestr("fake_file", b"fake content")

    zf = zipfile.ZipFile(compressed_project)
    new_dir = tmp_path / "new_dir"
    setup_project_directory(zf, new_dir, [])

    mocked_log.assert_called_with("Creating project dir {!r}", str(new_dir))
    assert "Extracting pyempaq content" in logs.debug
    assert new_dir.exists()
    assert (new_dir / "fake_file").read_text() == "fake content"


def test_projectdir_already_there():
    """Don't do anything if project exists from before."""
    fixme


def test_projectdir_requirements():
    """Project with virtualenv requirements."""
    fixme
