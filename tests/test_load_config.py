# Copyright 2021 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Tests for the argument processing."""

import pathlib
import sys

import pytest

from pyempaq.config_manager import load_config, ConfigError, _format_pydantic_errors


@pytest.fixture
def drive_letter():
    """Provide a drive letter under windows, so paths can be made absolute."""
    return 'c:' if sys.platform == 'win32' else ''


# -- basic problems

def test_missing_source_file(tmp_path):
    """The indicated source file does not exist."""
    config_file = tmp_path / "config.yaml"
    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert str(cm.value) == f"Configuration file not found: {str(config_file)!r}"


def test_missing_source_in_dir(tmp_path):
    """The indicate directory does not have an useful file."""
    with pytest.raises(ConfigError) as cm:
        load_config(tmp_path)
    assert str(cm.value) == f"Configuration file not found: {str(tmp_path / 'pyempaq.yaml')!r}"


def test_bad_source(tmp_path):
    """Cannot parse the indicated source file."""
    config_file = tmp_path / "pyempaq.yaml"
    config_file.write_text("x: [a, ")
    with pytest.raises(ConfigError) as cm:
        load_config(tmp_path)
    assert str(cm.value) == f"Cannot open and parse YAML configuration file {str(config_file)!r}"


# -- general sanity case

def test_basic_mandatory_all_ok(tmp_path):
    """Config structure ok, using a script."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            script: script.py
    """)
    script = tmp_path / "script.py"
    script.write_text("test script content")

    config = load_config(config_file)
    assert config.basedir == tmp_path
    assert (config.basedir / config.exec.script).read_text() == "test script content"
    assert config.exec.module is None
    assert config.exec.entrypoint is None
    assert config.exec.default_args == []
    assert config.requirements == []


# -- base directory alternatives

def test_paths_relative_to_basedir_absolute(tmp_path):
    """Basedir (specified absolute) works as a default dir."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"""
        name: testproject
        basedir: {tmp_path  / 'projectdir'}
        exec:
            script: script.py
    """)
    projectdir = tmp_path / "projectdir"
    projectdir.mkdir()
    script = projectdir / "script.py"
    script.write_text("test script content")

    config = load_config(config_file)
    assert config.basedir == projectdir
    assert (config.basedir / config.exec.script).read_text() == "test script content"


def test_paths_relative_to_basedir_relative(tmp_path):
    """Basedir (specified relative) works as a default dir."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        basedir: projectdir
        exec:
            script: script.py
    """)
    projectdir = tmp_path / "projectdir"
    projectdir.mkdir()
    script = projectdir / "script.py"
    script.write_text("test script content")

    config = load_config(config_file)
    assert config.basedir == projectdir
    assert (config.basedir / config.exec.script).read_text() == "test script content"


def test_paths_relative_to_basedir_userhome(tmp_path, monkeypatch):
    """Basedir (specified with user home) works as a default dir."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        basedir: ~/projectdir
        exec:
            script: script.py
    """)
    projectdir = tmp_path / "projectdir"
    projectdir.mkdir()
    script = projectdir / "script.py"
    script.write_text("test script content")

    monkeypatch.setenv("HOME", str(tmp_path))  # posix
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # windows
    config = load_config(config_file)
    assert config.basedir == projectdir
    assert (config.basedir / config.exec.script).read_text() == "test script content"


def test_basedir_not_a_directory(tmp_path):
    """The base directory must be a directory."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"""
        name: testproject
        basedir: {tmp_path / 'config.yaml'}
        exec:
            script: script.py
    """)

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        f"- 'basedir': path {str(tmp_path / 'config.yaml')!r} must be a directory",
        f"- 'exec.script': path {str(tmp_path / 'config.yaml/script.py')!r} not found",
    ]


def test_basedir_missing(tmp_path):
    """The base directory must exist."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        basedir: whatever
        exec:
            script: script.py
    """)

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        f"- 'basedir': path {str(tmp_path / 'whatever')!r} not found",
        f"- 'exec.script': path {str(tmp_path / 'whatever/script.py')!r} not found",
    ]


def test_minimum_req_version_not_a_string(tmp_path):
    """The minimum_python_version must be a string."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        unpack_restrictions:
            minimum_python_version: 3.8
    """)

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        "- 'exec': field required",
        "- 'unpack_restrictions': 3.8 must be a string",
    ]


# -- check the different exec entries

def test_exec_script_ok_relative(tmp_path):
    """Check script subkey to be ok and relative."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            script: script.py
    """)
    script = tmp_path / "script.py"
    script.touch()

    config = load_config(config_file)
    assert config.exec.script == pathlib.Path("script.py")  # relative!
    assert config.exec.module is None
    assert config.exec.entrypoint is None


def test_exec_script_missing(tmp_path):
    """Check script subkey not found."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            script: script.py
    """)

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        f"- 'exec.script': path {str(tmp_path / 'script.py')!r} not found",
    ]


def test_exec_script_outside_project(tmp_path):
    """Check script is inside project."""
    config_file = tmp_path / "project" / "config.yaml"
    config_file.parent.mkdir()
    config_file.write_text("""
        name: testproject
        exec:
            script: ../script.py
    """)
    script = tmp_path / "script.py"
    script.touch()

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        "- 'exec.script': relative path must be inside the packed project",
    ]


def test_exec_script_absolute(tmp_path, drive_letter):
    """Check script subkey using an absolute path."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"""
        name: testproject
        exec:
            script: {drive_letter}/media/foobar/script.py
    """)

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        "- 'exec.script': path must be relative",
    ]


def test_exec_script_not_a_file(tmp_path):
    """Check script subkey pointing not to a file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            script: script.py
    """)
    script = tmp_path / "script.py"
    script.mkdir()

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        f"- 'exec.script': path {str(tmp_path / 'script.py')!r} must be a file",
    ]


def test_exec_module_ok_relative(tmp_path):
    """Check module subkey to be ok and relative."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            module: foobar
    """)
    module = tmp_path / "foobar"
    module.mkdir()

    config = load_config(config_file)
    assert config.exec.script is None
    assert config.exec.module == pathlib.Path("foobar")  # relative!
    assert config.exec.entrypoint is None


def test_exec_module_missing(tmp_path):
    """Check module subkey not found."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            module: foobar
    """)

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        f"- 'exec.module': path {str(tmp_path / 'foobar')!r} not found",
    ]


def test_exec_module_outside_project(tmp_path):
    """Check module is inside project."""
    config_file = tmp_path / "project" / "config.yaml"
    config_file.parent.mkdir()
    config_file.write_text("""
        name: testproject
        exec:
            module: ../foobar
    """)
    module = tmp_path / "foobar"
    module.mkdir()

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        "- 'exec.module': relative path must be inside the packed project",
    ]


def test_exec_module_absolute(tmp_path, drive_letter):
    """Check module subkey using absoule path."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"""
        name: testproject
        exec:
            module: {drive_letter}/tmp/foobar
    """)

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        "- 'exec.module': path must be relative",
    ]


def test_exec_entrypoint_format_ok(tmp_path):
    """Check the entry point format, success."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: [foo, bar]
    """)

    config = load_config(config_file)
    assert config.exec.entrypoint == ["foo", "bar"]


def test_exec_entrypoint_format_bad_internal_type(tmp_path):
    """Check the entry point format, problems."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: [33, "foo"]
    """)

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        "- 'exec.entrypoint[0]': str type expected",
    ]


def test_exec_entrypoint_format_bad_not_list(tmp_path):
    """Check the entry point format, problems."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: stuff
    """)

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        "- 'exec.entrypoint': value is not a valid list",
    ]


def test_exec_default_args_format_ok(tmp_path):
    """Check the default args format, success."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: ["-x", "go"]
            default-args: [foo, bar]
    """)

    config = load_config(config_file)
    assert config.exec.default_args == ["foo", "bar"]


def test_exec_default_args_format_bad_internal_type(tmp_path):
    """Check the default args format, problems."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: ["-x", "go"]
            default-args: [33, "foo"]
    """)

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        "- 'exec.default-args[0]': str type expected",
    ]


def test_exec_default_args_format_bad_not_list(tmp_path):
    """Check the default args format, problems."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: ["-x", "go"]
            default-args: stuff
    """)

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        "- 'exec.default-args': value is not a valid list",
    ]


def test_exec_xor_none(tmp_path):
    """At least one of the needed execution items is needed."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            default-args: [a, b]
    """)

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        "- 'exec': need at least one of these subkeys: 'script', 'module', 'entrypoint'",
    ]


@pytest.mark.parametrize("combo", [
    ["script: foo", "module: bar"],
    ["script: foo", "entrypoint: baz"],
    ["module: bar", "entrypoint: baz"],
    ["script: foo", "module: bar", "entrypoint: baz"],
])
def test_exec_xor_bad_combos(tmp_path, combo):
    """Only one of the needed execution items is allowed."""
    config_file = tmp_path / "config.yaml"
    with config_file.open("wt") as fh:
        fh.write("name: testproject\n")
        fh.write("exec:\n")
        for line in combo:
            fh.write(f"    {line}\n")

    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        "- 'exec': only one of these subkeys is allowed: 'script', 'module', 'entrypoint'",
    ]


# -- tests for requirements files and dependencies

def test_reqdeps_requirements_ok(tmp_path):
    """Config with requirements indicated, all ok."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: ["foo", "bar"]
        requirements:
            - reqs1.txt
    """)
    reqs_file = tmp_path / "reqs1.txt"
    reqs_file.touch()
    config = load_config(config_file)
    assert config.requirements == [pathlib.Path("reqs1.txt")]


def test_reqdeps_requirements_absolute(tmp_path, drive_letter):
    """Requirements file is absolute."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"""
        name: testproject
        exec:
            entrypoint: ["foo", "bar"]
        requirements:
            - {drive_letter}/tmp/reqs1.txt
    """)
    reqs_file = tmp_path / "reqs1.txt"
    reqs_file.touch()
    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        "- 'requirements[0]': path must be relative",
    ]


def test_reqdeps_requirements_missing(tmp_path):
    """Requirements file is not there."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: ["foo", "bar"]
        requirements:
            - reqs1.txt
    """)
    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        f"- 'requirements[0]': path {str(tmp_path / 'reqs1.txt')!r} not found",
    ]


def test_reqdeps_requirements_inside_project(tmp_path):
    """Requirements file is not inside the project."""
    config_file = tmp_path / "project" / "config.yaml"
    config_file.parent.mkdir()
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: ["foo", "bar"]
        requirements:
            - ../reqs1.txt
    """)
    reqs_file = tmp_path / "reqs1.txt"
    reqs_file.touch()
    with pytest.raises(ConfigError) as cm:
        load_config(config_file)
    assert cm.value.errors == [
        "- 'requirements[0]': relative path must be inside the packed project",
    ]


def test_reqdeps_dependencies_ok(tmp_path):
    """Config with dependencies indicated, all ok."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
        name: testproject
        exec:
            entrypoint: ["foo", "bar"]
        dependencies:
            - foo
            - bar
    """)
    reqs_file = tmp_path / "reqs1.txt"
    reqs_file.touch()
    config = load_config(config_file)
    assert config.dependencies == [
        "foo",
        "bar",
    ]


# -- tests for the error formatter

def test_error_formatter_simple_field(tmp_path):
    """The location is simple."""
    pydantic_errors = [
        {'loc': ('name',), 'msg': 'field required', 'type': 'value_error.missing'},
    ]
    errors = _format_pydantic_errors(pydantic_errors)
    assert errors == [
        "- 'name': field required",
    ]


def test_error_formatter_deep_field(tmp_path):
    """The location is nested."""
    pydantic_errors = [
        {'loc': ('exec', 'script'), 'msg': 'file must exist', 'type': 'value_error'},
    ]
    errors = _format_pydantic_errors(pydantic_errors)
    assert errors == [
        "- 'exec.script': file must exist",
    ]


def test_error_formatter_index(tmp_path):
    """The location has an index."""
    pydantic_errors = [
        {'loc': ('exec', 'script', 3, 'stuff'), 'msg': 'file must exist', 'type': 'value_error'},
    ]
    errors = _format_pydantic_errors(pydantic_errors)
    assert errors == [
        "- 'exec.script[3].stuff': file must exist",
    ]


def test_error_formatter_multiple_results(tmp_path):
    """The formatting handle multiple results."""
    pydantic_errors = [
        {'loc': ('name',), 'msg': 'field required', 'type': 'value_error.missing'},
        {'loc': ('exec', 'script'), 'msg': 'file must exist', 'type': 'value_error'},
    ]
    errors = _format_pydantic_errors(pydantic_errors)
    assert errors == [
        "- 'name': field required",
        "- 'exec.script': file must exist",
    ]
