# Copyright 2022 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Common functionality for packer and unpucker modules."""

import logging
import subprocess


logger = logging.getLogger('logger')


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
