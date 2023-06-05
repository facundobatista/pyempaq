# Copyright 2021 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""The configuration manager."""

import pathlib
from typing import List

import pydantic
import yaml


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


class ModelConfigDefaults(
        pydantic.BaseModel, extra=pydantic.Extra.forbid, frozen=True, validate_all=True):
    """Define defaults for the BaseModel configuration."""


class CustomStrictStr(pydantic.StrictStr):
    """Generic class to create custom strict strings validated by pydantic."""

    @classmethod
    def __get_validators__(cls):
        """Yield the relevant validators."""
        yield from super().__get_validators__()
        yield cls.custom_validate


class RelativePath(CustomStrictStr):
    """Constrained string which must be a relative path."""

    @classmethod
    def custom_validate(cls, value):
        """Validate."""
        if value is None:
            return
        value = pathlib.Path(value)

        if value.is_absolute():
            raise ValueError("path must be relative")

        # relative to the basedir
        abs_path = _BASEDIR / value

        if not abs_path.exists():
            raise ValueError(f"path {str(abs_path)!r} not found")

        if _BASEDIR not in abs_path.resolve().parents:
            raise ValueError("relative path must be inside the packed project")

        # return the relative path
        return value


class RelativeFile(RelativePath):
    """Constrained relative path which must be a file."""

    @classmethod
    def custom_validate(cls, value):
        """Validate."""
        value = super().custom_validate(value)
        if value is None:
            return

        # relative to the basedir
        abs_path = _BASEDIR / value

        if not abs_path.is_file():
            raise ValueError(f"path {str(abs_path)!r} must be a file")

        # return the relative path
        return value


class Executor(ModelConfigDefaults, alias_generator=lambda s: s.replace("_", "-")):
    """Executor information."""

    script: RelativeFile = None
    module: RelativePath = None
    entrypoint: List[pydantic.StrictStr] = None
    default_args: List[pydantic.StrictStr] = []


class UnpackRestrictions(ModelConfigDefaults, alias_generator=lambda s: s.replace("_", "-")):
    """Restrictions that will be verified/enforced during unpack."""

    minimum_python_version: pydantic.StrictStr = None


class Config(
    ModelConfigDefaults,
    validate_all=False,
    alias_generator=lambda s: s.replace("_", "-"),
):
    """Definition of PyEmpaq's configuration."""

    name: str
    basedir: pathlib.Path  # the default for this is managed on YAML load time
    exec: Executor
    requirements: List[RelativeFile] = []
    dependencies: List[str] = []
    include: List[str] = DEFAULT_INCLUDE_LIST
    exclude: List[str] = []
    unpack_restrictions: UnpackRestrictions = None

    @pydantic.validator("basedir")
    def ensure_basedir(cls, value):
        """Ensure that the basedir is valid, and store it to be used by other paths."""
        global _BASEDIR

        value = value.expanduser()
        if not value.is_absolute():
            value = _CONFIGDIR / value

        # set the basedir after the expanding/absolutizing, so the rest of the config can use it
        _BASEDIR = value

        if not value.exists():
            raise ValueError(f"path {str(value)!r} not found")
        if not value.is_dir():
            raise ValueError(f"path {str(value)!r} must be a directory")
        return value

    @pydantic.validator("exec", pre=True)
    def validate_exec_subkeys(cls, values):
        """Check the exec subkeys."""
        # it must be one, and only one, of these...
        subkeys = ["script", "module", "entrypoint"]
        count = sum(x in values for x in subkeys)
        if count == 0:
            subkeys_str = ', '.join(repr(x) for x in subkeys)
            raise ValueError(f"need at least one of these subkeys: {subkeys_str}")
        if count > 1:
            subkeys_str = ', '.join(repr(x) for x in subkeys)
            raise ValueError(f"only one of these subkeys is allowed: {subkeys_str}")
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

        message = error['msg'].strip()
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
        parsed = Config.parse_obj(content)
    except pydantic.error_wrappers.ValidationError as error:
        raise ConfigError(errors=_format_pydantic_errors(error.errors()))

    return parsed
