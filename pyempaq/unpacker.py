# Copyright 2021-2023 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Unpacking functionality.."""

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
from typing import List, Dict, Any

from packaging import version

from pyempaq.common import find_venv_bin, logged_exec


# this is the directory for the NEW virtualenv created for the project (not the packed
# one to run unpacker itself)
PROJECT_VENV_DIR = "project_venv"

# the file name to flag that the project setup completed succesfully
COMPLETE_FLAG_FILE = "complete.flag"

# setup logging
logger = logging.getLogger()
handler = logging.StreamHandler()
fmt = logging.Formatter("::pyempaq:: %(asctime)s %(message)s")
handler.setFormatter(fmt)
handler.setLevel(0)
logger.addHandler(handler)
logger.setLevel(logging.ERROR if os.environ.get("PYEMPAQ_DEBUG") is None else logging.INFO)
log = logger.info


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


def run_command(venv_bin_dir: pathlib.Path, cmd: List[str]) -> None:
    """Run the command with a custom context."""
    newenv = os.environ.copy()
    venv_bin_dir_str = str(venv_bin_dir)
    if "PATH" in newenv:
        newenv["PATH"] = newenv["PATH"] + ":" + venv_bin_dir_str
    else:
        newenv["PATH"] = venv_bin_dir_str
    newenv["PYEMPAQ_PYZ_PATH"] = os.path.dirname(__file__)
    subprocess.run(cmd, env=newenv)


def setup_project_directory(
    zf: zipfile.ZipFile,
    project_dir: pathlib.Path,
    venv_requirements: List[pathlib.Path],
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
            log("Reusing project dir %r", str(project_dir))
            return
        log("Found incomplete project dir %r", str(project_dir))
        shutil.rmtree(project_dir)
        log("Removed old incomplete dir")

    log("Creating project dir %r", str(project_dir))
    project_dir.mkdir()

    log("Extracting pyempaq content")
    zf.extractall(path=project_dir)

    if venv_requirements:
        log("Creating payload virtualenv")
        venv_dir = project_dir / PROJECT_VENV_DIR
        venv.create(venv_dir, with_pip=True)
        pip_exec = find_venv_bin(venv_dir, "pip3")
        cmd = [str(pip_exec), "install"]
        for req_file in venv_requirements:
            cmd += ["-r", str(req_file)]
        log("Installing dependencies: %s", cmd)
        logged_exec(cmd)
        log("Virtualenv setup finished")
    else:
        log("Skipping virtualenv (no requirements)")
    (project_dir / COMPLETE_FLAG_FILE).touch()


def restrictions_ok(restrictions: Dict[str, Any]) -> bool:
    """Enforce the unpacking restrictions, if any; return True if all ok to continue."""
    if not restrictions:
        return True
    ignored_restrictions = os.environ.get("PYEMPAQ_IGNORE_RESTRICTIONS", "").split(",")

    mpv = restrictions.get("minimum_python_version")
    if mpv is not None:
        current = platform.python_version()
        log("Checking minimum Python version: indicated=%r current=%r", mpv, current)
        if version.parse(mpv) > version.parse(current):
            msg = "Failed to comply with version restriction: need at least Python %s"
            if "minimum-python-version" in ignored_restrictions:
                logger.info("(ignored) " + msg, mpv)
            else:
                logger.error(msg, mpv)
                return False

    return True


def run():
    """Run the unpacker."""
    log("Pyempaq start")

    # parse pyempaq metadata from the zip file
    pyempaq_filepath = pathlib.Path.cwd() / sys.argv[0]
    zf = zipfile.ZipFile(pyempaq_filepath)
    metadata = json.loads(zf.read("metadata.json").decode("utf8"))
    log("Loaded metadata: %s", metadata)
    if not restrictions_ok(metadata["unpack_restrictions"]):
        exit(1)

    # load appdirs from the builtin venv
    sys.path.insert(0, f"{pyempaq_filepath}/venv/")
    import appdirs  # NOQA: this is an import not at top of file because paths needed to be fixed

    pyempaq_dir = pathlib.Path(appdirs.user_data_dir()) / 'pyempaq'
    pyempaq_dir.mkdir(parents=True, exist_ok=True)
    log("Temp base dir: %r", str(pyempaq_dir))

    # create a temp dir and extract the project there
    timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime(pyempaq_filepath.stat().st_ctime))
    project_dir = pyempaq_dir / "{}-{}".format(metadata["project_name"], timestamp)
    original_project_dir = project_dir / "orig"
    venv_requirements = [original_project_dir / fname for fname in metadata["requirement_files"]]
    setup_project_directory(zf, project_dir, venv_requirements)

    python_exec = get_python_exec(project_dir)
    os.chdir(original_project_dir)

    cmd = build_command(str(python_exec), metadata, sys.argv[1:])
    log("Running payload: %s", cmd)
    venv_bin_dir = python_exec.parent
    run_command(venv_bin_dir, cmd)
    log("Pyempaq done")


if __name__ == "__main__":
    run()
