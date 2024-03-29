# Copyright 2021-2023 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Unpacker tests."""

import hashlib
import json
import os
import platform
import textwrap
import time
import zipfile
from pathlib import Path
from subprocess import CompletedProcess

import platformdirs
import pytest
from logassert import Exact, NOTHING
from packaging import version

import pyempaq.unpacker
from pyempaq.unpacker import (
    FatalError,
    PROJECT_VENV_DIR,
    build_command,
    build_project_install_dir,
    enforce_restrictions,
    get_base_dir,
    run_command,
    setup_project_directory,
    special_action_info,
    special_action_uninstall,
)


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


def test_runcommand_with_env_path(monkeypatch, mocker):
    """Run a command with a PATH in the env."""
    cmd = ["foo", "bar"]
    monkeypatch.setenv("TEST_PYEMPAQ", "123")
    monkeypatch.setenv("PATH", "previous-path")

    run_mock = mocker.patch("subprocess.run")
    run_command(Path("test-venv-dir"), cmd)

    (call1,) = run_mock.call_args_list
    assert call1[0] == (cmd,)
    passed_env = call1[1]["env"]
    assert passed_env["TEST_PYEMPAQ"] == "123"
    assert passed_env["PATH"] == "previous-path:test-venv-dir"


def test_runcommand_no_env_path(monkeypatch, mocker):
    """Run a command without a PATH in the env."""
    cmd = ["foo", "bar"]
    monkeypatch.setenv("TEST_PYEMPAQ", "123")
    monkeypatch.delenv("PATH")

    run_mock = mocker.patch("subprocess.run")
    run_command(Path("test-venv-dir"), cmd)

    (call1,) = run_mock.call_args_list
    assert call1[0] == (cmd,)
    passed_env = call1[1]["env"]
    assert passed_env["TEST_PYEMPAQ"] == "123"
    assert passed_env["PATH"] == "test-venv-dir"


def test_runcommand_pyz_path(mocker):
    """Check the .pyz path is set."""
    run_mock = mocker.patch("subprocess.run")
    run_command(Path("test-venv-dir"), ["foo", "bar"])

    (call1,) = run_mock.call_args_list
    passed_env = call1[1]["env"]
    assert passed_env["PYEMPAQ_PYZ_PATH"] == os.path.dirname(pyempaq.unpacker.__file__)


def test_runcommand_returns_exit_code(mocker):
    """Check the completed process is returned."""
    cmd = ["foo", "bar"]
    code = 1
    mocker.patch("subprocess.run", return_value=CompletedProcess(cmd, code))
    proc = run_command(Path("test-venv-dir"), cmd)

    assert proc.args == cmd
    assert proc.returncode == code


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


def test_projectdir_already_there_complete_normal(tmp_path, logs):
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


def test_projectdir_already_there_complete_ephemeral(tmp_path, logs):
    """If project exists from before and is complete it's weird to be ephemeral."""
    # just create the new directory and flag it as done
    new_dir = tmp_path / "new_dir"
    new_dir.mkdir()
    (new_dir / "complete.flag").touch()

    # run the setup, if tries to re-create it or uncompress the project (zf is None!) it will crash
    zf = None
    setup_project_directory(zf, new_dir, [], ephemeral=True)

    assert "Reusing project dir '.*new_dir'" in logs.warning
    assert "Reusing project dir" not in logs.info
    assert "Creating project dir" not in logs.info
    assert "Skipping virtualenv" not in logs.info


def test_projectdir_requirements(tmp_path, logs, mocker):
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
    mocked_venv_create = mocker.patch("venv.create")
    mocked_find = mocker.patch("pyempaq.unpacker.find_venv_bin", return_value=fake_pip_path)
    mocked_exec = mocker.patch("pyempaq.unpacker.logged_exec")
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


def test_projectdir_metadata(tmp_path, logs):
    """Project directory without special requirements."""
    # fake a compressed project
    compressed_project = tmp_path / "project.zip"
    with zipfile.ZipFile(compressed_project, "w") as zf:
        zf.writestr("fake_file", b"fake content")

    # get its hash
    zipfile_hash = hashlib.sha256(compressed_project.read_bytes()).hexdigest()

    # unpack
    zf = zipfile.ZipFile(compressed_project)
    new_dir = tmp_path / "new_dir"
    before_timestamp = time.time()
    setup_project_directory(zf, new_dir, [])
    after_timestamp = time.time()

    # check metadata file
    unpack_metadata = json.loads((new_dir / "unpacking.json").read_text())
    assert unpack_metadata["pyz_path"] == str(compressed_project)
    assert unpack_metadata["pyz_hash"] == zipfile_hash
    stored_timestamp = unpack_metadata["timestamp"]
    assert before_timestamp <= stored_timestamp <= after_timestamp


# --- tests for enforcing the unpacking restrictions


@pytest.mark.parametrize("restrictions", [None, {}])
def test_enforcerestrictions_empty(restrictions, logs):
    """Support for no restrictions."""
    enforce_restrictions(version, restrictions)
    assert NOTHING in logs.any_level


def test_enforcerestrictions_pythonversion_smaller(logs):
    """Enforce minimum python version: smaller version."""
    enforce_restrictions(version, {"minimum_python_version": "0.8"})
    current = platform.python_version()
    assert f"Checking minimum Python version: indicated='0.8' current={current!r}" in logs.info
    assert NOTHING in logs.error


def test_enforcerestrictions_pythonversion_bigger_enforced(logs):
    """Enforce minimum python version: bigger version."""
    with pytest.raises(FatalError) as cm:
        enforce_restrictions(version, {"minimum_python_version": "42"})
    assert cm.value.returncode is FatalError.ReturnCode.restrictions_not_met
    current = platform.python_version()
    assert f"Checking minimum Python version: indicated='42' current={current!r}" in logs.info
    assert "Failed to comply with version restriction: need at least Python 42" in logs.error


def test_enforcerestrictions_pythonversion_bigger_ignored(logs, monkeypatch):
    """Ignore minimum python version for the bigger version case."""
    monkeypatch.setenv("PYEMPAQ_IGNORE_RESTRICTIONS", "minimum-python-version")
    enforce_restrictions(version, {"minimum_python_version": "42"})
    current = platform.python_version()
    assert f"Checking minimum Python version: indicated='42' current={current!r}" in logs.info
    assert Exact(
        "(ignored) Failed to comply with version restriction: need at least Python 42"
    ) in logs.info


def test_enforcerestrictions_pythonversion_current(logs):
    """Enforce minimum python version: exactly current version."""
    current = platform.python_version()
    enforce_restrictions(version, {"minimum_python_version": current})
    assert (
        f"Checking minimum Python version: indicated={current!r} current={current!r}" in logs.info
    )
    assert NOTHING in logs.error


def test_enforcerestrictions_pythonversion_good_comparison(logs):
    """Enforce minimum python version using a proper comparison, not strings."""
    enforce_restrictions(version, {"minimum_python_version": "3.0009"})


# --- tests for the project install dir name


def test_installdirname_complete(mocker, tmp_path):
    """Check the name is properly built."""
    mocker.patch("platform.python_implementation", return_value="PyPy")
    mocker.patch("platform.python_version_tuple", return_value=("3", "18", "7alpha"))
    mocker.patch("pyempaq.unpacker.MAGIC_NUMBER", "xyz")

    zip_path = tmp_path / "somestuff.zip"
    content = b"some content to be hashed"
    zip_path.write_bytes(content)
    content_hash = hashlib.sha256(content).hexdigest()

    fake_metadata = {"foo": "bar", "project_name": "testproj"}

    dirname = build_project_install_dir(zip_path, fake_metadata)

    assert dirname == f"testproj-{content_hash[:20]}-pypy.3.18.xyz"


def test_installdirname_custombase_default(mocker, tmp_path):
    """The location of base directory is the default."""
    mocker.patch.object(platformdirs, "user_data_dir", return_value=tmp_path)

    dirpath = get_base_dir(platformdirs)
    assert dirpath == tmp_path / "pyempaq"
    assert dirpath.exists()
    assert dirpath.is_dir()


def test_installdirname_custombase_set_ok(monkeypatch, tmp_path):
    """Set the location of base directory through the env var."""
    custom_basedir = tmp_path / "testbase"
    custom_basedir.mkdir()
    monkeypatch.setenv("PYEMPAQ_UNPACK_BASE_PATH", str(custom_basedir))

    dirpath = get_base_dir(platformdirs)
    assert dirpath == custom_basedir
    assert dirpath.exists()
    assert dirpath.is_dir()


def test_installdirname_custombase_missing(monkeypatch, tmp_path):
    """The indicated base directory location does not exist."""
    custom_basedir = tmp_path / "testbase"
    monkeypatch.setenv("PYEMPAQ_UNPACK_BASE_PATH", str(custom_basedir))

    with pytest.raises(FatalError) as cm:
        get_base_dir(platformdirs)
    assert cm.value.returncode is FatalError.ReturnCode.unpack_basedir_missing


def test_installdirname_custombase_not_dir(monkeypatch, tmp_path):
    """The indicated base directory location is not a directory."""
    custom_basedir = tmp_path / "testbase"
    custom_basedir.touch()  # not a directory!!
    monkeypatch.setenv("PYEMPAQ_UNPACK_BASE_PATH", str(custom_basedir))

    with pytest.raises(FatalError) as cm:
        get_base_dir(platformdirs)
    assert cm.value.returncode is FatalError.ReturnCode.unpack_basedir_notdir


# --- tests for the special actions


def test_specialaction_info_simple(tmp_path, capsys):
    """A couple of installs to show."""
    (tmp_path / "testproj-whatever-123").mkdir()
    (tmp_path / "testproj-another one").mkdir()
    special_action_info(tmp_path, {"project_name": "testproj"})

    out, _ = capsys.readouterr()
    assert out == textwrap.dedent(f"""\
        Base PyEmpaq directory: {tmp_path}
        Current installations:
            testproj-another one
            testproj-whatever-123
    """)


def test_specialaction_info_nothing(tmp_path, capsys):
    """No install to show information."""
    special_action_info(tmp_path, {"project_name": "testproj"})

    out, _ = capsys.readouterr()
    assert out == textwrap.dedent(f"""\
        Base PyEmpaq directory: {tmp_path}
        No installation found!
    """)


def test_specialaction_uninstall_simple(tmp_path, capsys):
    """Some installs to remove."""
    inst1 = tmp_path / "testproj-whatever-123"
    inst1.mkdir()
    inst2 = tmp_path / "testproj-another one"
    inst2.mkdir()
    special_action_uninstall(tmp_path, {"project_name": "testproj"})

    out, _ = capsys.readouterr()
    assert out == textwrap.dedent("""\
        Removing installation:
            testproj-another one
            testproj-whatever-123
    """)
    assert not inst1.exists()
    assert not inst2.exists()


def test_specialaction_uninstall_nothing(tmp_path, capsys):
    """No install to remove."""
    special_action_uninstall(tmp_path, {"project_name": "testproj"})

    out, _ = capsys.readouterr()
    assert out == textwrap.dedent("""\
        No installation found!
    """)
