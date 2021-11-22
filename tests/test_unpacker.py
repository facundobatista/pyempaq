# Copyright 2021 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Unpacker tests."""

from pyempaq.unpacker import build_command


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
