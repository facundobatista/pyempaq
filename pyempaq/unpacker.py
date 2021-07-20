import json
import os
import pathlib
import subprocess
import sys
import time
import venv
import zipfile


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


def log(template, *args):
    """Print debug lines if proper envvar is present."""
    # ToDo: only log if STOWER_DEBUG=1
    print("::pyempaq::", template.format(*args))


def get_python_exec(project_dir):
    """Return the Python exec to use.

    If a venv is present (just created or from a previous unpack) use it, else just use
    the one used to run this script.
    """
    venv_dir = project_dir / "venv"
    if venv_dir.exists():
        executable = find_venv_bin(venv_dir, "python")
    else:
        executable = sys.executable
    return executable


log("Pyempaq start")

# parse pyempaq metadata from the zip file
pyempaq_filepath = pathlib.Path.cwd() / sys.argv[0]
zf = zipfile.ZipFile(pyempaq_filepath)
metadata = json.loads(zf.read("metadata.json").decode("utf8"))
log("Loaded metadata: {}", metadata)

# load appdirs from the builtin venv
sys.path.insert(0, f"{pyempaq_filepath}/venv/")
import appdirs  # NOQA: this is an import not at top of file because paths needed to be fixed

pyempaq_dir = pathlib.Path(appdirs.user_data_dir()) / 'pyempaq'
pyempaq_dir.mkdir(parents=True, exist_ok=True)
log("Temp base dir: {!r}", str(pyempaq_dir))

# create a temp dir and extract the project there
timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime(pyempaq_filepath.stat().st_ctime))
project_dir = pyempaq_dir / "{}-{}".format(metadata["project_name"], timestamp)
original_project_dir = project_dir / "orig"
if project_dir.exists():
    log("Reusing project dir {!r}", str(project_dir))
else:
    log("Creating project dir {!r}", str(project_dir))
    project_dir.mkdir()

    log("Extracting pyempaq content")
    zf.extractall(path=project_dir)

    venv_requirements = metadata["requirement_files"]
    if venv_requirements:
        log("Creating payload virtualenv")
        venv_dir = project_dir / "venv"
        venv.create(venv_dir, with_pip=True)
        pip_exec = find_venv_bin(venv_dir, "pip")
        cmd = [pip_exec, "install"]
        for req_file in venv_requirements:
            cmd += ["-r", str(original_project_dir / req_file)]
        log("Installing dependencies: {}", cmd)
        subprocess.run(cmd, check=True)  # ToDo absorb outputs here
        log("Virtualenv setup finished")

    else:
        log("Skipping virtualenv (no requirements)")

python_exec = get_python_exec(project_dir)
log("Running payload using {!r}", python_exec)
os.chdir(original_project_dir)
cmd = [python_exec, metadata["entrypoint"]]
subprocess.run(cmd)
log("Pyempaq done")
