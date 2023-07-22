# Copyright 2021-2023 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Unpacking functionality.."""

import enum
import hashlib
import importlib
import json
import logging
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import time
import venv
import zipfile
from types import ModuleType
from typing import List, Dict, Any

from pyempaq.common import find_venv_bin, logged_exec


# this is the directory for the NEW virtualenv created for the project (not the packed
# one to run unpacker itself)
PROJECT_VENV_DIR = "project_venv"

# the file name to flag that the project setup completed successfully
COMPLETE_FLAG_FILE = "complete.flag"

# the real magic number is a byte sequence with "\r\n" at the end; it's built here
# so it's easily patchable by tests
MAGIC_NUMBER = importlib.util.MAGIC_NUMBER[:-2].hex()

# setup logging
logger = logging.getLogger()
handler = logging.StreamHandler()
fmt = logging.Formatter("::pyempaq:: %(asctime)s %(message)s")
handler.setFormatter(fmt)
handler.setLevel(0)
logger.addHandler(handler)
logger.setLevel(logging.ERROR if os.environ.get("PYEMPAQ_DEBUG") is None else logging.INFO)


class FatalError(Exception):
    """Error that will terminate the unpacking.

    This is never shown to the user, but the overall process will exit with
    the indicated return code.
    """

    class ReturnCode(enum.IntEnum):
        """Codes that the unpacker may return."""

        restrictions_not_met = 64
        unpack_basedir_missing = 65
        unpack_basedir_notdir = 66

    def __init__(self, code):
        self.returncode = code
        super().__init__("")


def get_python_exec(project_dir: pathlib.Path) -> pathlib.Path:
    """Return the Python exec to use.

    If a venv is present (just created or from a previous unpack) use it, else just use
    the one used to run this script.
    """
    venv_dir = project_dir / PROJECT_VENV_DIR
    if venv_dir.exists():
        executable = find_venv_bin(venv_dir, "python")
    else:
        executable = pathlib.Path(sys.executable)
    return executable


def build_command(python_exec: str, metadata: Dict[str, str], sys_args: List[str]) -> List[str]:
    """Build the command to be executed."""
    if metadata["exec_style"] == "script":
        cmd = [python_exec, metadata["exec_value"]]
    elif metadata["exec_style"] == "module":
        cmd = [python_exec, "-m", metadata["exec_value"]]
    elif metadata["exec_style"] == "entrypoint":
        cmd = [python_exec] + metadata["exec_value"]

    if sys_args:
        cmd.extend(sys_args)
    else:
        cmd.extend(metadata["exec_default_args"])
    return cmd


def run_command(venv_bin_dir: pathlib.Path, cmd: List[str]) -> subprocess.CompletedProcess:
    """Run the command with a custom context."""
    newenv = os.environ.copy()
    venv_bin_dir_str = str(venv_bin_dir)
    if "PATH" in newenv:
        newenv["PATH"] = newenv["PATH"] + ":" + venv_bin_dir_str
    else:
        newenv["PATH"] = venv_bin_dir_str
    newenv["PYEMPAQ_PYZ_PATH"] = os.path.dirname(__file__)
    return subprocess.run(cmd, env=newenv)


def get_file_hexdigest(filepath: pathlib.Path) -> str:
    """Hash a file and return its hexdigest."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as fh:
        while True:
            data = fh.read(65536)
            hasher.update(data)
            if not data:
                break
    return hasher.hexdigest()


def setup_project_directory(
    zf: zipfile.ZipFile,
    project_dir: pathlib.Path,
    venv_requirements: List[pathlib.Path],
    *,
    ephemeral=False,
):
    """Set up the project directory (if needed).

    Process in case it's needed:

    - create the directory

    - extract everything from the zipfile into the new directory

    - if there are virtualenv dependencies:

        - create the virtualenv

        - install dependencies there

    After successful set up a flag is left in the directory so next time the unpacker is run
    it recognizes everything is done (note that having the directory is not enough, it may
    have been partially set up).
    """
    if project_dir.exists():
        if (project_dir / COMPLETE_FLAG_FILE).exists():
            log_call = logger.warning if ephemeral else logger.info
            log_call("Reusing project dir %r", str(project_dir))
            return
        logger.info("Found incomplete project dir %r", str(project_dir))
        shutil.rmtree(project_dir)
        logger.info("Removed old incomplete dir")

    logger.info("Creating project dir %r", str(project_dir))
    project_dir.mkdir()

    logger.info("Extracting pyempaq content")
    zf.extractall(path=project_dir)

    if venv_requirements:
        logger.info("Creating payload virtualenv")
        venv_dir = project_dir / PROJECT_VENV_DIR
        venv.create(venv_dir, with_pip=True)
        pip_exec = find_venv_bin(venv_dir, "pip3")
        cmd = [str(pip_exec), "install"]
        for req_file in venv_requirements:
            cmd += ["-r", str(req_file)]
        logger.info("Installing dependencies: %s", cmd)
        logged_exec(cmd)
        logger.info("Virtualenv setup finished")
    else:
        logger.info("Skipping virtualenv (no requirements)")

    # store unpacking metadata
    zf_hash = get_file_hexdigest(zf.filename)
    metadata = {
        "pyz_path": str(zf.filename),
        "pyz_hash": zf_hash,
        "timestamp": time.time(),
    }
    (project_dir / "unpacking.json").write_text(json.dumps(metadata))

    # save the flag for completeness
    (project_dir / COMPLETE_FLAG_FILE).touch()


def enforce_restrictions(version: ModuleType, restrictions: Dict[str, Any]) -> bool:
    """Enforce the unpacking restrictions, if any; raise a fatal error if they are not met."""
    if not restrictions:
        return
    ignored_restrictions = os.environ.get("PYEMPAQ_IGNORE_RESTRICTIONS", "").split(",")

    mpv = restrictions.get("minimum_python_version")
    if mpv is not None:
        current = platform.python_version()
        logger.info("Checking minimum Python version: indicated=%r current=%r", mpv, current)
        if version.parse(mpv) > version.parse(current):
            msg = "Failed to comply with version restriction: need at least Python %s"
            if "minimum-python-version" in ignored_restrictions:
                logger.info("(ignored) " + msg, mpv)
            else:
                logger.error(msg, mpv)
                raise FatalError(FatalError.ReturnCode.restrictions_not_met)


def build_project_install_dir(zip_path: pathlib.Path, metadata: Dict[str, str]):
    """Build the name of the directory where everything will be extracted."""
    project_name = metadata["project_name"]

    # get the first part of the hash of the file
    hexdigest = get_file_hexdigest(zip_path)
    file_hash_partial = hexdigest[:20]

    # Python details
    py_impl = platform.python_implementation().lower()
    py_version = ".".join(platform.python_version_tuple()[:2])

    name = f"{project_name}-{file_hash_partial}-{py_impl}.{py_version}.{MAGIC_NUMBER}"
    return name


def get_base_dir(platformdirs: ModuleType) -> pathlib.Path:
    """Get the base directory for all PyEmpaq installs.

    If it's indicated by the user, it must exist and be a directory (less error prone
    this way). If it's the default, this function ensures it is created.

    It needs to receive the 'platformdirs' because it's imported from the builtin
    virtualenv (not generically available).
    """
    custom_basedir = os.environ.get("PYEMPAQ_UNPACK_BASE_PATH")
    if custom_basedir is None:
        basedir = pathlib.Path(platformdirs.user_data_dir()) / 'pyempaq'
        basedir.mkdir(parents=True, exist_ok=True)
    else:
        basedir = pathlib.Path(custom_basedir)
        if not basedir.exists():
            raise FatalError(FatalError.ReturnCode.unpack_basedir_missing)
        if not basedir.is_dir():
            raise FatalError(FatalError.ReturnCode.unpack_basedir_notdir)

    return basedir


def run():
    """Run the unpacker."""
    logger.info("PyEmpaq start")

    # parse pyempaq metadata from the zip file
    pyempaq_filepath = pathlib.Path.cwd() / sys.argv[0]
    zf = zipfile.ZipFile(pyempaq_filepath)
    metadata = json.loads(zf.read("metadata.json").decode("utf8"))
    logger.info("Loaded metadata: %s", metadata)

    # load platformdirs and packaging from the builtin venv (not at top of file because
    # paths needed to be fixed)
    sys.path.insert(0, f"{pyempaq_filepath}/venv/")
    import platformdirs  # NOQA
    from packaging import version  # NOQA

    # check all restrictions are met
    enforce_restrictions(version, metadata["unpack_restrictions"])

    pyempaq_dir = get_base_dir(platformdirs)
    logger.info("Base directory: %r", str(pyempaq_dir))

    # create a temp dir and extract the project there
    project_dir = pyempaq_dir / build_project_install_dir(pyempaq_filepath, metadata)
    original_project_dir = project_dir / "orig"
    venv_requirements = [original_project_dir / fname for fname in metadata["requirement_files"]]
    ephemeral = os.environ.get("PYEMPAQ_EPHEMERAL")
    setup_project_directory(zf, project_dir, venv_requirements, ephemeral=ephemeral)

    python_exec = get_python_exec(project_dir)
    original_process_directory = os.getcwd()
    os.chdir(original_project_dir)

    cmd = build_command(str(python_exec), metadata, sys.argv[1:])
    logger.info("Running payload: %s", cmd)
    venv_bin_dir = python_exec.parent
    proc = run_command(venv_bin_dir, cmd)
    logger.info("Exit code: %s", proc.returncode)

    if ephemeral:
        logger.info("Removing project install directory because ephemeral indicated.")
        os.chdir(original_process_directory)
        shutil.rmtree(project_dir)
    logger.info("PyEmpaq done")
    return proc.returncode


if __name__ == "__main__":
    try:
        rc = run()
    except FatalError as error:
        rc = error.returncode
    exit(rc)
