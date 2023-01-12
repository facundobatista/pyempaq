# Copyright 2021-2023 Facundo Batista
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

    # write the proper config
    config = tmp_path / "pyempaq.yaml"
    config.write_text(textwrap.dedent(f"""
        name: testproject
        basedir: {projectpath}
        exec:
          script: ep.py
        requirements:
            - requirements.txt
    """))

    # pack it calling current pyempaq externally
    env = dict(os.environ)  # need to replicate original env because of Windows
    env["PYTHONPATH"] = os.getcwd()
    cmd = [sys.executable, "-m", "pyempaq", str(config)]
    os.chdir(projectpath)
    subprocess.run(cmd, check=True, env=env)
    packed_filepath = projectpath / "testproject.pyz"
    assert packed_filepath.exists()

    # run the packed file in a clean directory
    cleandir = tmp_path / "cleandir"
    cleandir.mkdir()
    packed_filepath.rename(cleandir / "testproject.pyz")
    os.chdir(cleandir)
    cmd = [sys.executable, "testproject.pyz"]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        env={"PYEMPAQ_DEBUG": "0"},
    )
    assert proc.returncode == 0, repr(proc.stdout)
    assert proc.stdout == textwrap.dedent("""\
        run ok
        internal module ok
        internal binary ok
        virtualenv module ok
    """)
