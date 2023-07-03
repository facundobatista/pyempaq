# Copyright 2021-2023 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Integration tests."""

import os
import subprocess
import sys
import textwrap

import pytest
import yaml

from pyempaq.unpacker import EXIT_CODES


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
    subprocess.run(cmd, check=True, env=env, capture_output=True)
    packed_filepath = tmp_path / "testproject.pyz"
    assert packed_filepath.exists()

    return packed_filepath


def _run_pack(packed_filepath, basedir):
    """Run the packed project in clean directory.

    Returns the process and the pack's final path.
    """
    # run the packed file in a clean directory
    cleandir = basedir / "cleandir"
    cleandir.mkdir()
    new_path = packed_filepath.rename(cleandir / "testproject.pyz")
    os.chdir(cleandir)
    cmd = [sys.executable, "testproject.pyz"]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    return proc, new_path


@pytest.mark.parametrize("expected_code", [0, 1])
def test_basic_cycle_full(tmp_path, monkeypatch, expected_code):
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
    entrypoint.write_text(textwrap.dedent(f"""
        import os

        print("run ok")

        from src import foo
        print("internal module ok")

        os.access(os.path.join("media", "bar.bin"), os.R_OK)
        print("internal binary ok")

        import requests
        assert "pyempaq" in requests.__file__
        print("virtualenv module ok")
        exit({expected_code})
    """))
    binarypath = projectpath / "media" / "bar.bin"
    binarypath.parent.mkdir()
    binarypath.write_bytes(b"123")
    modulepath = projectpath / "src" / "foo.py"
    modulepath.parent.mkdir()
    modulepath.write_text("pass")

    packed_filepath = _pack(tmp_path, monkeypatch, f"""
        name: testproject
        basedir: {projectpath}
        exec:
          script: ep.py
        dependencies: [requests]
    """)

    proc, _ = _run_pack(packed_filepath, tmp_path)
    assert proc.returncode == expected_code, repr(proc.stdout)
    assert proc.stdout == textwrap.dedent("""\
        run ok
        internal module ok
        internal binary ok
        virtualenv module ok
    """)


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

    proc, run_path = _run_pack(packed_filepath, tmp_path)
    output_lines = [line for line in proc.stdout.split("\n") if line]
    assert proc.returncode == 0, "\n".join(output_lines)

    # verify output
    (exposed_pyz_path,) = output_lines
    assert exposed_pyz_path == str(run_path)


@pytest.mark.parametrize("expected_code,extraconf,log", [
    (
        EXIT_CODES["restrictions_not_met"],
        {"unpack-restrictions": {"minimum-python-version": "99.99"}},
        "Failed to comply with version restriction: need at least Python"
    )
])
def test_special_exit_codes(tmp_path, monkeypatch, expected_code, extraconf, log):
    """Test special exit codes returned by pyempaq."""
    projectpath = tmp_path / "fakeproject"
    projectpath.mkdir()
    (projectpath / "main.py").write_text("exit(0)")
    conf = {
        "name": "testproject",
        "basedir": str(projectpath),
        "exec": {
            "script": "main.py"
        },
        **extraconf
    }
    packed_filepath = _pack(projectpath, monkeypatch, yaml.safe_dump(conf))
    proc, _ = _run_pack(packed_filepath, tmp_path)

    assert proc.returncode == expected_code
    assert log in proc.stdout or ""


@pytest.mark.parametrize("extraconf", [
    # the default scenario, all project files are included
    {},
    # the include scenario with requirements explicitly included
    {"include": ["main.py", "req1.txt", "req2.txt"]}
])
def test_pack_with_requirements(tmp_path, monkeypatch, extraconf):
    """Test pack with provided requirements works."""
    projectpath = tmp_path / "fakeproject"
    projectpath.mkdir()
    (projectpath / "req1.txt").write_text("requests")
    (projectpath / "req2.txt").touch()
    (projectpath / "main.py").write_text("import requests;print('ok')")
    conf = {
        "name": "testproject",
        "basedir": str(projectpath),
        "requirements": ["req1.txt", "req2.txt"],
        "exec": {
            "script": "main.py"
        },
        **extraconf
    }
    packed_filepath = _pack(projectpath, monkeypatch, yaml.safe_dump(conf))
    proc, _ = _run_pack(packed_filepath, tmp_path)

    assert proc.returncode == 0
    assert proc.stdout.strip() == "ok"


def test_pack_exits_on_requirements_non_included(tmp_path, monkeypatch):
    """Test pack behaviour for missing requirements.

    A project is not packed when some requirements are not included in it
    via the "include" config.
    """
    projectpath = tmp_path / "fakeproject"
    projectpath.mkdir()
    reqs = ["req1.txt", "req2.txt"]
    for req in reqs:
        # don't include a package to speedup the test
        (projectpath / req).touch()
    (projectpath / "main.py").write_text("print('ok')")
    conf = {
        "name": "testproject",
        "basedir": str(projectpath),
        "include": ["main.py"],
        "requirements": reqs,
        "exec": {
            "script": "main.py"
        },
    }

    with pytest.raises(subprocess.CalledProcessError) as exc:
        _pack(projectpath, monkeypatch, yaml.safe_dump(conf))

    error = (
        "ERROR Pack error: The indicated requirements "
        "['req1.txt', 'req2.txt'] "
        "are not included along the packed files; ensure to include them "
        "explicitly in the config."
    ).encode()
    assert exc.value.returncode == 2
    assert error in exc.value.stderr
