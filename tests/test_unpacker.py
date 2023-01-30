# Copyright 2021-2023 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Unpacker tests."""

import zipfile
from pathlib import Path
from unittest.mock import patch

from logassert import Exact

from pyempaq.unpacker import build_command, run_command, setup_project_directory, PROJECT_VENV_DIR


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


def test_projectdir_simple(tmp_path, logs):
    """Project directory without special requirements."""
    # fake a compressed project
    compressed_project = tmp_path / "project.zip"
    with zipfile.ZipFile(compressed_project, "w") as zf:
        zf.writestr("fake_file", b"fake content")

    zf = zipfile.ZipFile(compressed_project)
    new_dir = tmp_path / "new_dir"
    setup_project_directory(zf, new_dir, [])

    assert "Creating project dir '.*new_dir'" in logs.info
    assert "Extracting pyempaq content" in logs.info
    assert "Skipping virtualenv" in logs.info
    assert new_dir.exists()
    assert (new_dir / "fake_file").read_text() == "fake content"
    assert (new_dir / "complete.flag").exists()


def test_projectdir_already_there_incomplete(tmp_path, logs):
    """Re install everything if project exists but is not complete."""
    # just create the new directory, no "complete" flag
    new_dir = tmp_path / "new_dir"
    new_dir.mkdir()

    # fake a compressed project
    compressed_project = tmp_path / "project.zip"
    with zipfile.ZipFile(compressed_project, "w") as zf:
        zf.writestr("fake_file", b"fake content")

    # run the setup
    zf = zipfile.ZipFile(compressed_project)
    setup_project_directory(zf, new_dir, [])

    assert "Found incomplete project dir '.*new_dir'" in logs.info
    assert "Removed old incomplete dir" in logs.info
    assert "Creating project dir" in logs.info
    assert "Skipping virtualenv" in logs.info


def test_projectdir_already_there_complete(tmp_path, logs):
    """Don't do anything if project exists from before and is complete."""
    # just create the new directory and flag it as done
    new_dir = tmp_path / "new_dir"
    new_dir.mkdir()
    (new_dir / "complete.flag").touch()

    # run the setup, if tries to re-create it or uncompress the project (zf is None!) it will crash
    zf = None
    setup_project_directory(zf, new_dir, [])

    assert "Reusing project dir '.*new_dir'" in logs.info
    assert "Creating project dir" not in logs.info
    assert "Skipping virtualenv" not in logs.info


def test_projectdir_requirements(tmp_path, logs):
    """Project with virtualenv requirements."""
    # fake a compressed project
    compressed_project = tmp_path / "project.zip"
    with zipfile.ZipFile(compressed_project, "w") as zf:
        zf.writestr("fake_file", b"fake content")

    zf = zipfile.ZipFile(compressed_project)
    new_dir = tmp_path / "new_dir"
    requirements = ["reqs1.txt", "reqs2.txt"]

    # the virtualenv creation and dependencies installation is a complicated dance that needs
    # to be patched:
    #   - the venv creation
    #   - the pip binary needs to be found inside that (mocked) virtualenv
    #   - the command uses that pip binary
    fake_pip_path = tmp_path / "pip"
    with patch("venv.create") as mocked_venv_create:
        with patch("pyempaq.unpacker.find_venv_bin", return_value=fake_pip_path) as mocked_find:
            with patch("pyempaq.unpacker.logged_exec") as mocked_exec:
                setup_project_directory(zf, new_dir, requirements)

    # check the calls to the mocked parts
    venv_dir = new_dir / PROJECT_VENV_DIR
    mocked_venv_create.assert_called_once_with(venv_dir, with_pip=True)
    mocked_find.assert_called_once_with(venv_dir, "pip3")
    install_command = [str(fake_pip_path), "install", "-r", "reqs1.txt", "-r", "reqs2.txt"]
    mocked_exec.assert_called_once_with(install_command)

    # logs for bootstrap and virtualenv installation
    assert "Creating project dir '.*new_dir'" in logs.info
    assert "Extracting pyempaq content" in logs.info
    assert "Creating payload virtualenv" in logs.info
    assert Exact(f"Installing dependencies: {install_command}") in logs.info
    assert "Virtualenv setup finished" in logs.info
