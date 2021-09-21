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
import uuid
import venv
import zipapp
from collections import namedtuple

from pyempaq.config_manager import load_config, ConfigError

# collected arguments
Args = namedtuple("Args", "project_name basedir entrypoint requirement_files")


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
    print("DEBUG packer: saving metadata from config", config)
    metadata = {
        "requirement_files": [str(path) for path in config.requirements],
        "project_name": config.name,
        "exec_default_args": config.exec.default_args,
    }
    if config.exec.script is not None:
        metadata["exec_style"] = "script"
        metadata["exec_value"] = str(config.exec.script)
    elif config.exec.module is not None:
        metadata["exec_style"] = "module"
        metadata["exec_value"] = str(config.exec.module)
    elif config.exec.entrypoint is not None:
        metadata["exec_style"] = "entrypoint"
        metadata["exec_value"] = str(config.exec.entrypoint)

    # if dependencies, store them just as another requirement file (save it inside the project,
    # but using an unique name to not overwrite anything)
    if config.dependencies:
        unique_name = f"pyempaq-autoreq-{uuid.uuid4()}.txt"
        extra_deps = origdir / unique_name
        extra_deps.write_text("\n".join(config.dependencies))
        metadata["requirement_files"].append(unique_name)

    metadata_file = tmpdir / "metadata.json"
    with metadata_file.open("wt", encoding="utf8") as fh:
        json.dump(metadata, fh)

    # create the zipfile
    packed_filepath = f"{config.name}.pyz"
    zipapp.create_archive(tmpdir, packed_filepath)

    # clean the temporary directory
    shutil.rmtree(tmpdir)

    print("Done, project packed in", packed_filepath)


def main():
    """Manage CLI interaction and call pack."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "source", type=pathlib.Path,
        help="The source file (pyempaq.yaml) or the directory where to find it.")
    args = parser.parse_args()
    try:
        print(f"Parsing configuration in {str(args.source)!r}")
        config = load_config(args.source)
    except ConfigError as err:
        print(err, file=sys.stderr)
        for err in err.errors:
            print(err, file=sys.stderr)
        exit(1)

    pack(config)
