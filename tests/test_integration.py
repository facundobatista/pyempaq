# Copyright 2021 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Integration tests."""

import os
import subprocess
import sys
import textwrap


def test_basic_cycle_full(tmp_path):
    """Verify that the sane packing/unpacking works.

    This checks that the unpacked/run project can:
    - run
    - import internal modules
    - access internal binaries
    - import modules from declared dependencies
    """
    # set up a basic test project, with an entrypoint that shows access to internals
    projectpath = tmp_path / "fakeproject"
    entrypoint = projectpath / "ep.py"
    entrypoint.parent.mkdir()
    entrypoint.write_text(textwrap.dedent("""
        import os

        print("run ok")

        from src import foo
        print("internal module ok")

        os.access(os.path.join("media", "bar.bin"), os.R_OK)
        print("internal binary ok")

        import requests
        assert "pyempaq" in requests.__file__
        print("virtualenv module ok")
    """))
    binarypath = projectpath / "media" / "bar.bin"
    binarypath.parent.mkdir()
    binarypath.write_bytes(b"123")
    modulepath = projectpath / "src" / "foo.py"
    modulepath.parent.mkdir()
    modulepath.write_text("pass")
    reqspath = projectpath / "requirements.txt"
    reqspath.write_text("requests")

    # pack it calling current pyempaq externally
    env = dict(os.environ)  # need to replicate original env because of Windows
    env["PYTHONPATH"] = os.getcwd()
    cmd = [
        sys.executable, "-m", "pyempaq",
        str(projectpath), str(entrypoint), "--requirement={}".format(reqspath)]
    os.chdir(projectpath)
    subprocess.run(cmd, check=True, env=env)
    packed_filepath = projectpath / "projectname.pyz"
    assert packed_filepath.exists()

    # run the packed file in a clean directory
    cleandir = tmp_path / "cleandir"
    cleandir.mkdir()
    packed_filepath.rename(cleandir / "projectname.pyz")
    os.chdir(cleandir)
    cmd = [sys.executable, "projectname.pyz"]
    proc = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, universal_newlines=True)
    output_lines = proc.stdout.split("\n")

    # verify output
    # XXX Facundo 2021-07-29: now we just check the info is there, in the future we want to check
    # that is ALL the output it was produced (need to fix some issues about unpacker verbosity)
    assert "run ok" in output_lines
    assert "internal module ok" in output_lines
    assert "internal binary ok" in output_lines
    assert "virtualenv module ok" in output_lines
