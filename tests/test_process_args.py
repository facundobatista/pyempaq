# Copyright 2021 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Tests for the argument processing."""

import pathlib
from argparse import Namespace

import pytest

from pyempaq.main import process_args, ArgumentsError


def test_all_ok_basic(tmp_path):
    """All arguments ok."""
    entrypoint = tmp_path / "script.py"
    entrypoint.touch()
    args = Namespace(basedir=tmp_path, entrypoint=entrypoint, requirement=None)
    processed = process_args(args)
    assert processed.basedir == tmp_path
    assert processed.entrypoint == pathlib.Path("script.py")  # relative!
    assert processed.requirement_files == []


def test_all_ok_with_requirements(tmp_path):
    """All ok, with a couple of requirement files."""
    entrypoint = tmp_path / "script.py"
    entrypoint.touch()
    req1 = tmp_path / "reqs-1.txt"
    req1.touch()
    req2 = tmp_path / "reqs-2.txt"
    req2.touch()
    args = Namespace(basedir=tmp_path, entrypoint=entrypoint, requirement=[req1, req2])
    processed = process_args(args)
    assert processed.basedir == tmp_path
    # all next paths relative to basedir
    assert processed.entrypoint == pathlib.Path("script.py")
    assert processed.requirement_files == [pathlib.Path("reqs-1.txt"), pathlib.Path("reqs-2.txt")]


def test_basedir_missing(tmp_path):
    """The base dir does not exist."""
    basedir = tmp_path / "foo"
    args = Namespace(basedir=basedir, entrypoint=None, requirement=None)
    with pytest.raises(ArgumentsError) as cm:
        process_args(args)
    assert str(cm.value) == f"Cannot find the base directory: {str(basedir)!r}."


def test_entrypoint_missing(tmp_path):
    """The entry point does not exist."""
    entrypoint = tmp_path / "script.py"
    args = Namespace(basedir=tmp_path, entrypoint=entrypoint, requirement=None)
    with pytest.raises(ArgumentsError) as cm:
        process_args(args)
    assert str(cm.value) == f"Cannot find the entrypoint: {str(entrypoint)!r}."


def test_entrypoint_outside_basedir(tmp_path):
    """The entry point is outside the base dir."""
    basedir = tmp_path / "foo"
    basedir.mkdir()
    entrypoint = tmp_path / "script.py"
    entrypoint.touch()
    args = Namespace(basedir=basedir, entrypoint=entrypoint, requirement=None)
    with pytest.raises(ArgumentsError) as cm:
        process_args(args)
    assert str(cm.value) == (
        f"The entrypoint {str(entrypoint)!r} must be inside the project {str(basedir)!r}.")


def test_entrypoint_deep_inside(tmp_path):
    """Sanity test with the entry point a couple of levels inside the project."""
    entrypoint = tmp_path / "foo" / "bar" / "script.py"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.touch()
    args = Namespace(basedir=tmp_path, entrypoint=entrypoint, requirement=None)
    processed = process_args(args)
    assert processed.entrypoint == pathlib.Path("foo") / "bar" / "script.py"  # still relative


def test_requirement_missing(tmp_path):
    """A requirement does not exist."""
    entrypoint = tmp_path / "script.py"
    entrypoint.touch()
    req = tmp_path / "reqs-1.txt"
    args = Namespace(basedir=tmp_path, entrypoint=entrypoint, requirement=[req])
    with pytest.raises(ArgumentsError) as cm:
        process_args(args)
    assert str(cm.value) == f"Cannot find the requirement file: {str(req)!r}."


def test_requirement_outside_basedir(tmp_path):
    """A requirement is outside the base dir."""
    basedir = tmp_path / "foo"
    basedir.mkdir()
    entrypoint = basedir / "script.py"
    entrypoint.touch()
    req = tmp_path / "reqs-1.txt"
    req.touch()
    args = Namespace(basedir=basedir, entrypoint=entrypoint, requirement=[req])
    with pytest.raises(ArgumentsError) as cm:
        process_args(args)
    assert str(cm.value) == (
        f"The requirement file {str(req)!r} must be inside the project {str(basedir)!r}.")
