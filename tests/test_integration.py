# Copyright 2021 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Integration tests."""

import os
import subprocess
import sys
import textwrap


def _pack(tmp_path, monkeypatch, config_text):
    """Set up the project config and pack it."""
    # write the proper config
    config = tmp_path / "pyempaq.yaml"
    config.write_text(textwrap.dedent(config_text))

    # pack it calling current pyempaq externally
    env = dict(os.environ)  # need to replicate original env because of Windows
    env["PYTHONPATH"] = os.getcwd()
    cmd = [sys.executable, "-m", "pyempaq", str(config)]
    monkeypatch.chdir(tmp_path)
    subprocess.run(cmd, check=True, env=env)
    packed_filepath = tmp_path / "testproject.pyz"
    assert packed_filepath.exists()

    return packed_filepath


def test_basic_cycle_full(tmp_path, monkeypatch):
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
    """))
    # XXX Facundo 2021-08-01: this check is disabled until we discover why venv.create
    # not working in GA
    #
    #     import requests
    #     assert "pyempaq" in requests.__file__
    #     print("virtualenv module ok")
    # """))
    binarypath = projectpath / "media" / "bar.bin"
    binarypath.parent.mkdir()
    binarypath.write_bytes(b"123")
    modulepath = projectpath / "src" / "foo.py"
    modulepath.parent.mkdir()
    modulepath.write_text("pass")
    reqspath = projectpath / "requirements.txt"
    reqspath.write_text("requests")

    packed_filepath = _pack(tmp_path, monkeypatch, f"""
        name: testproject
        basedir: {projectpath}
        exec:
          script: ep.py
    """)

    # run the packed file in a clean directory
    cleandir = tmp_path / "cleandir"
    cleandir.mkdir()
    packed_filepath.rename(cleandir / "testproject.pyz")
    os.chdir(cleandir)
    cmd = [sys.executable, "testproject.pyz"]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    output_lines = proc.stdout.split("\n")
    assert proc.returncode == 0, "\n".join(output_lines)

    # verify output
    # XXX Facundo 2021-07-29: now we just check the info is there, in the future we want to check
    # that is ALL the output it was produced (need to fix some issues about unpacker verbosity)
    assert "run ok" in output_lines
    assert "internal module ok" in output_lines
    assert "internal binary ok" in output_lines
    # XXX Facundo 2021-08-01: this check is disabled until we discover why venv.create
    # not working in GA
    # assert "virtualenv module ok" in output_lines


def test_pyz_location(tmp_path, monkeypatch):
    """Check that the environment variable for the .pyz location is set."""
    # set up a basic test project, with an entrypoint that shows access to internals
    projectpath = tmp_path / "fakeproject"
    entrypoint = projectpath / "ep.py"
    entrypoint.parent.mkdir()
    entrypoint.write_text(textwrap.dedent("""
        import os

        print(os.environ.get("PYEMPAQ_PYZ_PATH"))
    """))

    packed_filepath = _pack(tmp_path, monkeypatch, f"""
        name: testproject
        basedir: {projectpath}
        exec:
          script: ep.py
    """)

    # run the packed file in a clean directory
    cleandir = tmp_path / "cleandir"
    cleandir.mkdir()
    packed_filepath.rename(cleandir / "renamed.pyz")
    os.chdir(cleandir)
    cmd = [sys.executable, "renamed.pyz"]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    output_lines = [line for line in proc.stdout.split("\n") if line]
    assert proc.returncode == 0, "\n".join(output_lines)

    # verify output
    (exposed_pyz_path,) = output_lines
    assert exposed_pyz_path == str(cleandir / "renamed.pyz")
