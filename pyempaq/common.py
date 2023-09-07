# Copyright 2022-2023 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Common functionality for packer and unpucker modules."""

import hashlib
import logging
import os
import pathlib
import subprocess


logger = logging.getLogger('logger')


class ExecutionError(Exception):
    """The subprocess didn't finish ok."""


class PackError(Exception):
    """An error occurred while packing the project."""


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
    logger.debug(f"Executing external command: {cmd}")
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    except Exception as err:
        raise ExecutionError(f"Command {cmd} crashed with {err!r}")
    stdout = []
    for line in proc.stdout:
        line = line[:-1]
        stdout.append(line)
        logger.debug(f":: {line}")
    retcode = proc.wait()
    if retcode:
        raise ExecutionError(f"Command {cmd} ended with retcode {retcode}")
    return stdout


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


def get_disknode_hexdigest(filepath: pathlib.Path) -> str:
    """Hash a disk node and return a hexdigest.

    The disk node can be a file (simple hashing) or a directory (hash all the content
    of all ordered files in the subtree).
    """
    if filepath.is_file():
        all_files = [filepath]
    else:
        all_files = []
        for basedir, dirnames, filenames in os.walk(filepath):
            all_files.extend(os.path.join(basedir, filename) for filename in filenames)

    hasher = hashlib.sha256()
    for filepath in sorted(all_files):
        with open(filepath, "rb") as fh:
            while True:
                data = fh.read(65536)
                hasher.update(data)
                if not data:
                    break
    return hasher.hexdigest()
