# Copyright 2021-2023 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""The configuration manager."""

import pathlib
from typing import List, Optional

import pydantic
import yaml
from typing_extensions import Annotated


# base directory to which the different included paths may be relative from
_BASEDIR = None

# directory where the config is taken from, which is the default for basedir
_CONFIGDIR = None

# the default include value to get all the project inside
DEFAULT_INCLUDE_LIST = ["./**"]


class ConfigError(Exception):
    """Specific errors found in the config."""

    def __init__(self, msg=None, errors=None):
        if msg is None:
            msg = "Problem(s) found in configuration file:"
        super().__init__(msg)
        if errors is None:
            errors = []
        self.errors = errors


def _relative_path_validator(value):
    """Constrained string which must be a relative path."""
    if value is None:
        return
    value = pathlib.Path(value)

    if value.is_absolute():
        raise AssertionError("path must be relative")

    # relative to the basedir
    abs_path = _BASEDIR / value

    if not abs_path.exists():
        raise AssertionError(f"path {str(abs_path)!r} not found")

    if _BASEDIR not in abs_path.resolve().parents:
        raise AssertionError("relative path must be inside the packed project")

    # return the relative path
    return value


def _relative_file_validator(value):
    """Constrained relative path which must be a file."""
    value = _relative_path_validator(value)
    if value is None:
        return

    # relative to the basedir
    abs_path = _BASEDIR / value

    if not abs_path.is_file():
        raise AssertionError(f"path {str(abs_path)!r} must be a file")

    # return the relative path
    return value


RelativePath = Annotated[str, pydantic.AfterValidator(_relative_path_validator)]
RelativeFile = Annotated[str, pydantic.AfterValidator(_relative_file_validator)]


class ModelConfigDefaults(pydantic.BaseModel):
    """Define defaults for the BaseModel configuration."""

    model_config = dict(
        extra="forbid",
        frozen=True,
        alias_generator=lambda s: s.replace("_", "-"),
    )


class Executor(ModelConfigDefaults, alias_generator=lambda s: s.replace("_", "-")):
    """Executor information."""

    script: Optional[RelativeFile] = None
    module: Optional[RelativePath] = None
    entrypoint: Optional[List[pydantic.StrictStr]] = None
    default_args: List[pydantic.StrictStr] = []


class UnpackRestrictions(ModelConfigDefaults, alias_generator=lambda s: s.replace("_", "-")):
    """Restrictions that will be verified/enforced during unpack."""

    minimum_python_version: pydantic.StrictStr = None


class Config(ModelConfigDefaults):
    """Definition of PyEmpaq's configuration."""

    name: str
    basedir: pathlib.Path  # the default for this is managed on YAML load time
    exec: Executor
    requirements: List[RelativeFile] = []
    dependencies: List[str] = []
    include: List[str] = DEFAULT_INCLUDE_LIST
    exclude: List[str] = []
    unpack_restrictions: Optional[UnpackRestrictions] = None

    @pydantic.field_validator("basedir")
    def ensure_basedir(cls, value):
        """Ensure that the basedir is valid, and store it to be used by other paths."""
        global _BASEDIR

        value = value.expanduser()
        if not value.is_absolute():
            value = _CONFIGDIR / value

        # set the basedir after the expanding/absolutizing, so the rest of the config can use it
        _BASEDIR = value

        if not value.exists():
            raise AssertionError(f"path {str(value)!r} not found")
        if not value.is_dir():
            raise AssertionError(f"path {str(value)!r} must be a directory")
        return value

    @pydantic.field_validator("exec", mode="before")
    def validate_exec_subkeys(cls, values):
        """Check the exec subkeys."""
        # it must be one, and only one, of these...
        subkeys = ["script", "module", "entrypoint"]
        count = sum(key in values for key in subkeys)
        if count == 0:
            subkeys_str = ', '.join(repr(x) for x in subkeys)
            raise AssertionError(f"need at least one of these subkeys: {subkeys_str}")
        if count > 1:
            subkeys_str = ', '.join(repr(x) for x in subkeys)
            raise AssertionError(f"only one of these subkeys is allowed: {subkeys_str}")
        return values


def _format_pydantic_errors(errors):
    """Format pydantic errors for a simpler presentation."""
    formated_errors = []
    for error in errors:
        # format location
        loc_parts = []
        for part in error['loc']:
            if isinstance(part, int):
                # an index, fix previous part
                loc_parts[-1] = f"{loc_parts[-1]}[{part}]"
            else:
                loc_parts.append(str(part))
        location = ".".join(loc_parts)

        message = error['msg'].strip().removeprefix("Assertion failed, ")
        formated_errors.append(f"- {location!r}: {message}")

    return formated_errors


def load_config(path):
    """Load the config from charmcraft.yaml in the indicated directory."""
    global _CONFIGDIR

    path = path.expanduser().absolute()
    if path.is_dir():
        _CONFIGDIR = path
        configpath = path / "pyempaq.yaml"
    else:
        _CONFIGDIR = path.parent
        configpath = path

    if not configpath.exists():
        raise ConfigError(f"Configuration file not found: {str(configpath)!r}")

    try:
        content = yaml.safe_load(configpath.read_text())
    except Exception:
        raise ConfigError(f"Cannot open and parse YAML configuration file {str(configpath)!r}")

    # if `basedir` defaults to the directory where the configuration exists
    if "basedir" not in content:
        content["basedir"] = configpath.parent

    try:
        parsed = Config.model_validate(content)
    except pydantic.ValidationError as error:
        raise ConfigError(errors=_format_pydantic_errors(error.errors()))

    return parsed
