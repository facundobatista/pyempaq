# Copyright 2021-2023 Facundo Batista
# Licensed under the GPL v3 License
# For further info, check https://github.com/facundobatista/pyempaq

"""Main packer module."""

import argparse
import errno
import glob
import json
import logging
import os
import pathlib
import shutil
import tempfile
import uuid
import venv
import zipapp
from collections import namedtuple
from pathlib import Path
from typing import List

from pyempaq import __version__
from pyempaq.common import find_venv_bin, logged_exec, ExecutionError
from pyempaq.config_manager import load_config, ConfigError, Config


# setup logging
logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-5s %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

# collected arguments
Args = namedtuple("Args", "project_name basedir entrypoint requirement_files")


def get_pip():
    """Ensure an usable version of `pip`."""
    useful_pip = Path("pip3")
    # try to see if it's already installed
    try:
        logged_exec([useful_pip, "--version"])
    except ExecutionError:
        # failed to find a runnable pip, we need to install one
        pass
    else:
        return useful_pip

    # no useful pip found, let's create a virtualenv and use the one inside
    tmpdir = Path(tempfile.mkdtemp())
    venv.create(tmpdir, with_pip=True)
    useful_pip = find_venv_bin(tmpdir, "pip3")
    return useful_pip


def copy_project(src_dir: Path, dest_dir: Path, include: List[str], exclude: List[str]):
    """Copy/link the selected project content from the source to the destination directory.

    The content is selected with the 'include' list of patterns, minus the 'exclude' ones.

    It works differently for the different node types:
    - regular files: hard links (unless permission error or cross device)
    - directories: created
    - symlinks: respected, validating that they don't link to outside
    - other types (blocks, mount points, etc): ignored
    """
    included_nodes = {}  # use a dict because we want to avoid duplicates, but we care about order
    included_nodes["."] = None  # always the root, to create the destination directory
    excluded_nodes = set()

    # XXX Facundo 2023-04-07: this whole try/finally around changing directories can be
    # simplified to just pass `root_dir` to `glob.glob` when we stop supporting < 3.10
    _original_dir = os.getcwd()
    os.chdir(src_dir)
    try:
        for pattern in include:
            items = glob.glob(pattern, recursive=True)
            if items:
                included_nodes.update(dict.fromkeys(items))
            else:
                logger.error("Cannot find nodes for specified pattern: %r", pattern)

        # get all excluded nodes, building the source path so it's
        # easier comparable in the main loop below
        for pattern in exclude:
            excluded_nodes.update(src_dir / path for path in glob.iglob(pattern, recursive=True))
    finally:
        os.chdir(_original_dir)

    # need to remove all content inside symlinked directories (as that symlink will
    # be reproduced, so those contents don't need to be particularly handled)
    symlinked_dirs = set()
    for node in included_nodes:
        node = src_dir / node
        if node.is_dir() and node.is_symlink():
            symlinked_dirs.add(node)

    def _relative(node):
        """Return str'ed node relative to src_dir, ready to log."""
        return str(node.relative_to(src_dir))

    for node in included_nodes:
        src_node = src_dir / node
        dest_node = dest_dir / node

        if src_node in excluded_nodes:
            logger.debug("Ignoring excluded node: %r", _relative(src_node))
            continue
        if any(parent in excluded_nodes for parent in src_node.parents):
            logger.debug("Ignoring node because excluded parent: %r", _relative(src_node))
            continue
        if any(parent in symlinked_dirs for parent in src_node.parents):
            # node is inside a symlinked path, no need to duplicate it
            continue

        # if included node is only part of subtree, ensure parent directories are there
        if not dest_node.parent.exists():
            dest_node.parent.mkdir(parents=True)

        if src_node.is_symlink():
            real_pointed_node = src_node.resolve()
            if src_dir not in real_pointed_node.parents:
                logger.debug(
                    "Ignoring symlink because targets outside the project: %r -> %r",
                    _relative(src_node), str(real_pointed_node),
                )
                continue
            relative_link = os.path.relpath(real_pointed_node, src_node.parent)
            target_is_dir = real_pointed_node.is_dir()  # needed for Windows
            dest_node.symlink_to(relative_link, target_is_directory=target_is_dir)

        elif src_node.is_dir():
            dest_node.mkdir(mode=src_node.stat().st_mode, exist_ok=True)

        elif src_node.is_file():
            try:
                # XXX Facundo 2023-04-07: we can use simpler `dest_node.hardlink_to(src_node)`
                # when we stop supporting < 3.10
                os.link(src_node, dest_node)
            except OSError as error:
                if error.errno != errno.EXDEV and not isinstance(error, PermissionError):
                    raise
                shutil.copy2(src_node, dest_node)

        else:
            logger.debug("Ignoring file because of type: %r", _relative(src_node))


def prepare_metadata(origdir: pathlib.Path, config: Config):
    """Prepare the meta-data for the future unpacker action.

    Note that all paths in the config are all already validated to exist
    and relative to the base directory (so no "place adaptation" needs
    to happen for the unpacking).
    """
    # store the needed metadata
    logger.debug("Saving metadata from config %s", config)
    metadata = {
        "requirement_files": [str(path) for path in config.requirements],
        "project_name": config.name,
        "exec_default_args": config.exec.default_args,
        "unpack_restrictions": dict(config.unpack_restrictions or {}),
    }
    if config.exec.script is not None:
        metadata["exec_style"] = "script"
        metadata["exec_value"] = str(config.exec.script)
    elif config.exec.module is not None:
        metadata["exec_style"] = "module"
        metadata["exec_value"] = str(config.exec.module)
    elif config.exec.entrypoint is not None:
        metadata["exec_style"] = "entrypoint"
        metadata["exec_value"] = str(config.exec.entrypoint)

    # if dependencies, store them just as another requirement file (save it inside the project,
    # but using an unique name to not overwrite anything)
    if config.dependencies:
        unique_name = f"pyempaq-autoreq-{uuid.uuid4()}.txt"
        extra_deps = origdir / unique_name
        extra_deps.write_text("\n".join(config.dependencies) + "\n")
        metadata["requirement_files"].append(unique_name)

    return metadata


def pack(config):
    """Pack."""
    project_root = Path(__file__).parent
    tmpdir = Path(tempfile.mkdtemp())
    logger.debug("Working in temp dir %r", str(tmpdir))

    # copy all the project content inside "orig" in temp dir
    origdir = tmpdir / "orig"
    copy_project(config.basedir, origdir, config.include, config.exclude)

    # copy the common module
    pyempaq_dir = tmpdir / "pyempaq"
    pyempaq_dir.mkdir()
    common_src = project_root / "common.py"
    common_final_src = tmpdir / "pyempaq" / "common.py"
    shutil.copy(common_src, common_final_src)

    # copy the unpacker as the entry point of the zip
    unpacker_src = project_root / "unpacker.py"
    unpacker_final_main = tmpdir / "__main__.py"
    shutil.copy(unpacker_src, unpacker_final_main)

    # build a dir with the dependencies needed by the unpacker
    logger.debug("Building internal dependencies dir")
    venv_dir = tmpdir / "venv"
    pip = get_pip()
    cmd = [pip, "install", "appdirs", f"--target={venv_dir}"]
    logged_exec(cmd)

    metadata = prepare_metadata(origdir, config)
    metadata_file = tmpdir / "metadata.json"
    with metadata_file.open("wt", encoding="utf8") as fh:
        json.dump(metadata, fh)

    # create the zipfile
    packed_filepath = f"{config.name}.pyz"
    zipapp.create_archive(tmpdir, packed_filepath)

    # clean the temporary directory
    shutil.rmtree(tmpdir)

    logger.info("Done, project packed in %r", str(packed_filepath))


def main():
    """Manage CLI interaction and call pack."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "source", type=Path,
        help="The source file (pyempaq.yaml) or the directory where to find it.")
    parser.add_argument(
        '-v', '--verbose',
        help="Show detailed information, typically of interest only when diagnosing problems.",
        action="store_const", dest="loglevel", const=logging.DEBUG)
    parser.add_argument(
        '-q', '--quiet',
        help="Only events of WARNING level and above will be tracked.",
        action="store_const", dest="loglevel", const=logging.WARNING)
    parser.add_argument(
        '-V', '--version',
        help="Print the version and exit.",
        action="version", version=__version__)
    args = parser.parse_args()

    if args.loglevel is not None:
        logging.getLogger().setLevel(args.loglevel)

    try:
        logger.info("Parsing configuration in %r", str(args.source))
        config = load_config(args.source)
    except ConfigError as err:
        logger.error(err)
        for err in err.errors:
            logger.error(err)
        exit(1)
    pack(config)
