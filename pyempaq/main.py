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
from pyempaq.config_manager import load_config, ConfigError


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
    included_nodes = ["."]  # always the root, to create the destination directory
    for pattern in include:
        included_nodes.extend(glob.iglob(pattern, root_dir=src_dir, recursive=True))

    # need to remove all content inside symlinked directories (as that symlink will
    # be reproduced, so those contents don't need to be particularly handled)
    symlinked_dirs = set()
    for node in included_nodes:
        node = src_dir / node
        if node.is_dir() and node.is_symlink():
            symlinked_dirs.add(node)
    included_nodes = [
        node for node in included_nodes
        if not any(parent in symlinked_dirs for parent in (src_dir / node).parents)
    ]

    # get all excluded nodes, building the source path so it's comparable below
    excluded_nodes = set()
    for pattern in exclude:
        excluded_nodes.update(
            src_dir / path
            for path in glob.iglob(pattern, root_dir=src_dir, recursive=True)
        )

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

        if src_node.is_symlink():
            real_pointed_node = src_node.resolve()
            if src_dir not in real_pointed_node.parents:
                logger.debug(
                    "Ignoring symlink because targets outside the project: %r -> %r",
                    _relative(src_node), str(real_pointed_node),
                )
                continue
            relative_link = os.path.relpath(real_pointed_node, src_node.parent)
            dest_node.symlink_to(relative_link)

        elif src_node.is_dir():
            dest_node.mkdir(mode=src_node.stat().st_mode, exist_ok=True)

        elif src_node.is_file():
            try:
                dest_node.hardlink_to(src_node)
            except OSError as error:
                if error.errno != errno.EXDEV and not isinstance(error, PermissionError):
                    raise
                shutil.copy2(src_node, dest_node)

        else:
            logger.debug("Ignoring file because of type: %r", _relative(src_node))


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

    # store the needed metadata
    logger.debug("Saving metadata from config %s", config)
    metadata = {
        "requirement_files": [str(path) for path in config.requirements],
        "project_name": config.name,
        "exec_default_args": config.exec.default_args,
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
        extra_deps.write_text("\n".join(config.dependencies))
        metadata["requirement_files"].append(unique_name)

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
