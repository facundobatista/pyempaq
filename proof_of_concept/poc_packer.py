#!/usr/bin/env python3

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import venv
import zipapp


class Error(Exception):
    """Flag an error."""
    def __init__(self, template, *args):
        super().__init__("")
        self.template = template
        self.args = args


def find_venv_bin(basedir, exec_base):  # ToDo: move this to a common place
    """Heuristics to find the pip executable in different platforms."""
    bin_dir = basedir / "bin"
    if bin_dir.exists():
        # linux-like environment
        return bin_dir / exec_base

    bin_dir = basedir / "Scripts"
    if bin_dir.exists():
        # windows environment
        return bin_dir / "{}.exe".format(exec_base)

    raise RuntimeError("Binary not found inside venv; subdirs: {}".format(list(basedir.iterdir())))


def get_pip():
    """Ensure an usable version of `pip`."""
    useful_pip = pathlib.Path("pip")
    # try to see if it's already installed
    proc = subprocess.run([useful_pip, "--version"])
    if proc.returncode != 0:
        tmpdir = pathlib.Path(tempfile.mkdtemp())
        venv.create(tmpdir, with_pip=True)
        useful_pip = find_venv_bin(tmpdir, "pip")
    return useful_pip


def main(project_name, basedir, entrypoint, requirement_files):
    """Pack."""
    # ToDo: show all DEBUG lines only on "verbose"
    print("DEBUG packer: validating args")
    # validate input and calculate the relative paths
    if not args.basedir.exists():
        raise Error("Cannot find the basedir: {!r}", str(args.basedir))
    args.basedir = "foo"
    if not entrypoint.exists():
        raise Error("Cannot find the entrypoint: {!r}", str(entrypoint))
    try:
        relative_entrypoint = entrypoint.relative_to(basedir)
    except ValueError:
        raise Error("The entrypoint must be inside the project tree with root {!r}", str(basedir))
    relative_requirements = []
    for req in requirement_files:
        if not req.exists():
            raise Error("Cannot find the requirement file: {!r}", str(req))
        try:
            relative_req = req.relative_to(basedir)
        except ValueError:
            raise Error(
                "The requirement file must be inside the project tree with root {!r}",
                str(basedir))
        relative_requirements.append(relative_req)

    tmpdir = pathlib.Path(tempfile.mkdtemp())
    print("DEBUG packer: working in temp dir {!r}".format(str(tmpdir)))

    # copy all the project content inside "orig" in temp dir
    origdir = tmpdir / "orig"
    shutil.copytree(basedir, origdir)

    # copy the unpacker as the entry point of the zip
    unpacker_final_main = tmpdir / "__main__.py"
    # ToDo: find the unpacker relatively to this code
    shutil.copy("poc_unpacker.py", unpacker_final_main)

    # build a dir with the dependencies needed by the unpacker
    print("DEBUG packer: building internal dependencies dir")
    venv_dir = tmpdir / "venv"
    pip = get_pip()
    cmd = [pip, "install", "appdirs", f"--target={venv_dir}"]
    subprocess.run(cmd, check=True)  # ToDo: absorb outputs

    # store the needed metadata
    print("DEBUG packer: saving metadata")
    metadata = {
        "entrypoint": str(relative_entrypoint),
        "requirement_files": [str(path) for path in relative_requirements],
        "project_name": project_name,
    }
    metadata_file = tmpdir / "metadata.json"
    with metadata_file.open("wt", encoding="utf8") as fh:
        json.dump(metadata, fh)

    # create the zipfile
    zipapp.create_archive(tmpdir, f"{project_name}.pyz")

    # clean the temporary directory
    shutil.rmtree(tmpdir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "basedir", type=pathlib.Path,
        help="Base directory, all its subtree will be packed.")
    parser.add_argument(
        "entrypoint", type=pathlib.Path,
        help="The file that should be executed to run the project.")
    parser.add_argument(
        "--requirement", type=pathlib.Path, action="append",
        help="Requirement file (this option can be used multiple times).")
    # ToDo: also support a "--from-setup" that gets ALL this from a project's setup.py
    args = parser.parse_args()

    # ToDo: get also the project name both from "args" and setup.py
    project_name = "projectname"

    requirements = args.requirement or []
    try:
        main(project_name, args.basedir, args.entrypoint, requirements)
    except Error as err:
        print("ERROR:", err.template.format(*err.args), file=sys.stderr)
