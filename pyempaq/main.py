# Copyright 2021 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Main packer module."""

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import venv
import zipapp
from collections import namedtuple

# collected arguments
Args = namedtuple("Args", "project_name basedir entrypoint requirement_files")


class ArgumentsError(Exception):
    """Flag an error with the given arguments."""


class ExecutionError(Exception):
    """The subprocess didn't finish ok."""


def find_venv_bin(basedir, exec_base):
    """Heuristics to find the pip executable in different platforms."""
    bin_dir = basedir / "bin"
    if bin_dir.exists():
        # linux-like environment
        return bin_dir / exec_base

    bin_dir = basedir / "Scripts"
    if bin_dir.exists():
        # windows environment
        return bin_dir / f"{exec_base}.exe"

    raise RuntimeError(f"Binary not found inside venv; subdirs: {list(basedir.iterdir())}")


def logged_exec(cmd):
    """Execute a command, redirecting the output to the log."""
    cmd = list(map(str, cmd))
    print(f"Executing external command: {cmd}")
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    except Exception as err:
        raise ExecutionError(f"Command {cmd} crashed with {err!r}")
    stdout = []
    for line in proc.stdout:
        line = line[:-1]
        stdout.append(line)
        print(f":: {line}")
    retcode = proc.wait()
    if retcode:
        raise ExecutionError(f"Command {cmd} ended with retcode {retcode}")
    return stdout


def get_pip():
    """Ensure an usable version of `pip`."""
    useful_pip = pathlib.Path("pip3")
    # try to see if it's already installed
    try:
        logged_exec([useful_pip, "--version"])
    except ExecutionError:
        # failed to find a runnable pip, we need to install one
        pass
    else:
        return useful_pip

    # no useful pip found, let's create a virtualenv and use the one inside
    tmpdir = pathlib.Path(tempfile.mkdtemp())
    venv.create(tmpdir, with_pip=True)
    useful_pip = find_venv_bin(tmpdir, "pip3")
    return useful_pip


def pack(config):
    """Pack."""
    tmpdir = pathlib.Path(tempfile.mkdtemp())
    print(f"DEBUG packer: working in temp dir {str(tmpdir)!r}")

    # copy all the project content inside "orig" in temp dir
    origdir = tmpdir / "orig"
    shutil.copytree(config.basedir, origdir)

    # copy the unpacker as the entry point of the zip
    unpacker_src = pathlib.Path(__file__).parent / "unpacker.py"
    unpacker_final_main = tmpdir / "__main__.py"
    shutil.copy(unpacker_src, unpacker_final_main)

    # build a dir with the dependencies needed by the unpacker
    print("DEBUG packer: building internal dependencies dir")
    venv_dir = tmpdir / "venv"
    pip = get_pip()
    cmd = [pip, "install", "appdirs", f"--target={venv_dir}"]
    logged_exec(cmd)

    # store the needed metadata
    print("DEBUG packer: saving metadata")
    metadata = {
        "entrypoint": str(config.entrypoint),
        "requirement_files": [str(path) for path in config.requirement_files],
        "project_name": config.project_name,
    }
    metadata_file = tmpdir / "metadata.json"
    with metadata_file.open("wt", encoding="utf8") as fh:
        json.dump(metadata, fh)

    # create the zipfile
    packed_filepath = f"{config.project_name}.pyz"
    zipapp.create_archive(tmpdir, packed_filepath)

    # clean the temporary directory
    shutil.rmtree(tmpdir)

    print("Done, project packed in packed_filepath")


def process_args(args):
    """Process and validate the received arguments."""
    project_name = "projectname"

    print("DEBUG packer: validating args")
    # validate input and calculate the relative paths
    if not args.basedir.exists():
        raise ArgumentsError(f"Cannot find the base directory: {str(args.basedir)!r}.")
    if not args.entrypoint.exists():
        raise ArgumentsError(f"Cannot find the entrypoint: {str(args.entrypoint)!r}.")
    try:
        relative_entrypoint = args.entrypoint.relative_to(args.basedir)
    except ValueError:
        raise ArgumentsError(
            f"The entrypoint {str(args.entrypoint)!r} must be inside "
            f"the project {str(args.basedir)!r}.")

    relative_requirements = []
    for req in (args.requirement or []):
        if not req.exists():
            raise ArgumentsError(f"Cannot find the requirement file: {str(req)!r}.")
        try:
            relative_req = req.relative_to(args.basedir)
        except ValueError:
            raise ArgumentsError(
                f"The requirement file {str(req)!r} must be "
                f"inside the project {str(args.basedir)!r}.")
        relative_requirements.append(relative_req)

    return Args(
        entrypoint=relative_entrypoint, basedir=args.basedir,
        requirement_files=relative_requirements, project_name=project_name)


def main():
    """Manage CLI interaction and call pack."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "basedir", type=pathlib.Path,
        help="Base directory, all its subtree will be packed.")
    parser.add_argument(
        "entrypoint", type=pathlib.Path,
        help="The file that should be executed to run the project.")
    parser.add_argument(
        "--requirement", type=pathlib.Path, action="append",
        help="Requirement file (this option can be used multiple times).")
    args = parser.parse_args()
    try:
        processed_args = process_args(args)
    except ArgumentsError as err:
        print("ERROR:", str(err), file=sys.stderr)
        exit(1)

    pack(processed_args)
