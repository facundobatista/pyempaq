# PyEmpaq

A simple but powerful Python packer to run any project with any virtualenv dependencies anywhwere.

With PyEmpaq you can convert any Python project (see limitations below) into a single `.pyz` file with all the project's content packed inside. 

Packing is super simple, see this demo:

![pack-demo](https://github.com/facundobatista/pyempaq/blob/main/resources/demo_pack.gif?raw=True)

That single file is everything that needs to be distributed. When the final user executes it, the original project will be expanded, its dependencies installed in a virtualenv, and then executed. Note that no special permissions or privileges are required, as everything happens in the user environment.

See that in action:

![run-demo](https://github.com/facundobatista/pyempaq/blob/main/resources/demo_run.gif?raw=True)

Both the packaging and the execution are fully multiplatorm. This means that you can pack a project in Linux, Windows, Mac or whatever, and it will run ok in Linux, Windows, Mac or whatever. The only requirement is Python to be already installed.

You can try yourself some packed with PyEmpaq examples, very easy, just download any of these files and run it with Python:

- [in a terminal](https://github.com/facundobatista/pyempaq/blob/main/examples/simple-command-line.pyz?raw=True): a very small pure terminal example (this, of course, needs to be run in a terminal)
- [a game](https://github.com/facundobatista/pyempaq/blob/main/examples/arcade-game.pyz?raw=True): a simple game using the [Python Arcade](https://api.arcade.academy/en/latest/) library (actually, it's the [example #6 from their tutorial](https://api.arcade.academy/en/latest/examples/platform_tutorial/step_06.html))
- [desktop app](https://github.com/facundobatista/pyempaq/blob/main/examples/desktop-qt-app.pyz?raw=True): a full-fledged desktop application using PyQt5 (this [Encuentro app](https://encuentro.taniquetil.com.ar/))

![logo](https://github.com/facundobatista/pyempaq/blob/main/resources/logo-256.png?raw=True)


You can install `pyempaq` directly from PyPI; see [instructions below](https://github.com/facundobatista/pyempaq#how-to-install-pyempaq).

PyEmpaq is security friendly, there is nothing obscure or secretly shipped when you distribute your project with it: anybody can just open the `pyz` file (it's just a ZIP) and inspect it.

It's also safe regarding licenses when distributing your packed software. Unlike packing mechanisms that rely on putting inside a big blob, with PyEmpaq you don't have to worry about the licenses of your software dependencies (and the dependencies' dependencies) in regard to distributing them.


### Limitations:

There are some limitations:

- Only Python >= 3.7 is supported

- Only Linux, Windows and Mac is supported

- Only pip-installable dependencies are supported (from PyPI or whatever).

- Only dependencies that are pure Python or provide wheels are supported.

All this means that the most majority of the projects could be packed and run by PyEmpaq. If you have any ideas on how to overcome any of these limitations, let's talk!


### How does this work?

There are two phases: packing and execution. 

The **packing phase** is executed by the project developer, only once, before distribution. It's a simple step where the developer runs PyEmpaq indicating all needed info, and PyEmpaq will produce a single `<projectname>.pyz` file. That's all, and that only file is what is needed for distribution.

In this packing phase, PyEmpaq builds the indicated packed file, putting inside:

- the payload project, with all the indicated modules and binary files

- an *unpacker* script from PyEmpaq, which will be run during the execution phase

- few more stuff: some needed infrastructure details for the `.pyz` to run correctly

After packing, the developer will distribute the packed file, final users will download/receive/get it, and execute it.

In the **execution phase** all that needs to be done by the final user is to run it using Python, which can be done from the command line (e.g. `python3 supergame.pyz`) or by doing double click from the file explorer in those systems that relate the `.pyz` extension to Python (e.g. Windows).

In this execution phase, the *unpacker* script put by PyEmpaq inside the packed file will be run, running the following steps:

- check if the needed setup exists from a previous run; if yes, it will just run the payload project with almost no extra work; otherwise...

- create a directory in the user data dir, and expand the `.pyz` file there

- create a virtualenv in that new directory, and install all the payload's project dependencies

- run the payload's project inside that virtualenv

The verification that the unpacker does to see if has a reusable setup from the past is based on the `.pyz` timestamp; if it changed (a new file was distributed), a new setup will be created and used.


## Command line options

There is one mandatory parameter:

- `source`: it needs to point the configuration file or to the directory where the configuration will be located (it will be searched by its default name `pyempaq.yaml`).

Examples:

- `pyempaq .`

- `pyempaq /data/project/`

- `pyempaq ~/repo/proj/config.yaml`

You can control verbosity by adding these command line parameters to control logging levels:

- `-v, --verbose` - Show detailed information, typically of interest only when diagnosing problems.
- `-q, --quiet` - Only events of WARNING level and above will be tracked.

All that said, there is an special option `-V, --version` that if used will just print the version and exit.

> **Note**
> In the **execution phase**, if you have an environment variable `PYEMPAQ_DEBUG=1` it will show the Pyempaq log lines during the execution.


## The configuration file

All the information that PyEmpaq needs to pack a project comes from a configuration file, which the developer would normally have in the project itself.

The following is the structure of the `pyempaq.yaml` configuration file:

- `name` [mandatory]: the name of the project.

- `basedir` [optional]: the project's base directory; if not included it defaults to where the configuration file is located.

- `exec` [mandatory]: the section where is defined the information to execute the project once unpacked; it holds different subkeys (some subkeys are marked with †: ONE of those keys must be present, but only ONE):

    - `script` [†]: the filepath of the python script to run; when unpacking PyEmpaq will do `python3 SCRIPT`.

    - `module` [†]: the name of the module to invoke; when unpacking PyEmpaq will do `python3 -m MODULE`.

    - `entrypoint` [†]: freeform, as a list of strings; when unpacking PyEmpaq will only insert the proper python3 at the beginning: `python3 STR1 STR2 ...`.

    - `default-args` [optional]: the default arguments to be passed to the script/module/entrypoint (if not overriden when the distributed `.pyz` is executed).

- `requirements` [optional]: a list of filepaths pointing to the requirement files with pip-installable dependencies.

- `dependencies` [optional]: a list of strings to directly specify packages to be installed by `pip` without needing to have a requirement file.

- `include` [optional]: a list of strings, each one specifying a pattern to decide what files and directories to include in the pack (see below); if not included it defaults to `["./**"]` which means all the files and directories in the project.

- `exclude` [optional]: a list of strings, each one specifying a pattern to decide what files and directories to exclude from the pack (see below).

- `unpack-restrictions` [optional]: a section to specify different restrictions to be verified/enforced during unpack.

    - `minimum-python-version` [optional]: a string specifying the minimum version possible to run correctly.

All specified filepaths must exist inside the project and must be relative (to the project's base directory), with the exception of `basedir` itself which can be absolute or relative (to the configuration file location).

Both `include` and `exclude` options use pattern matching according to the rules used by the Unix shell, using `*`, `?`, and character ranges expressed with `[]`. Also `**` will match any files and zero or more directories. For more information or subtleties check the [`glob.glob`](https://docs.python.org/dev/library/glob.html#glob.glob) documentation.

Note that the final user may ignore/bypass any unpack restrictions using the `PYEMPAQ_IGNORE_RESTRICTIONS` environment variable with a value of comma-separated names of which restrictions to ignore.

The following are examples of different configuration files (which were the ones used to build the packed examples mentioned before):

- [the terminal script](https://github.com/facundobatista/pyempaq/blob/main/examples/pyempaq-script.yaml?raw=True)

- [the simple game](https://github.com/facundobatista/pyempaq/blob/main/examples/pyempaq-game.yaml?raw=True)

- [the full desktop app](https://github.com/facundobatista/pyempaq/blob/main/examples/pyempaq-desktop-app.yaml?raw=True)


## Context of the project being run

When the packed script/module/whatever is run in the unpacking phase, it will be executed inside the virtualenv with the needed requirements/dependencies (freshly created and installed or reused from a previous run).

Also, the following environment variable will be set:

- `PYEMPAQ_PYZ_PATH`: the absolute path to the `.pyz` run by the user


## How to install PyEmpaq

Directly from PyPI:

    pip install --user --upgrade --ignore-installed pyempaq

It's handy to install it using `pipx`, if you have it:

    pipx install pyempaq

If you have `fades` you don't even need to install pyempaq, just run it:

    fades -d pyempaq -x pyempaq

In the future there will be more ways to install it. Please open an issue if you desire an installation method (extra points if you specify how), thanks!


## Try packing an example project

PyEmpaq sources come with a small example project if you want to play a little packing it. Just a couple of dir/files under `examples/srcproject`:

- a `src` and `media`, with stuff to be imported and accessed.

- a `pyempaq.yaml` with the configuration for PyEmpaq.

- a `ep.py` file which is the project's entrypoint; all it does is to inform it started, import the internal module, access the media files, and use the declared dependency, reporting every step.

- a `secrets.txt` file that must not be included in the packed file.

This explores most of the needs of any project. You can try this example, and surely after you will be ready to actually pack any other project you want.

So, let's pack the example source project. As you're working with the PyEmpaq project itself (as you're packing its example), you don't really need to have it installed yet. In that case, if you have `fades` installed is super easy:

    fades -r requirements.txt -m pyempaq examples/srcproject/

Otherwise, you would need to create and use a virtual environment:

    python3 -m venv env
    source env/bin/activate
    pip install -r requirements
    python3 -m pyempaq examples/srcproject/

After running that command, you will see a `pyempaq-example.pyz` file. That is the **whole project encoded in a single file**.

At this point you may move that `pyempaq-example.pyz` to another directory, or to another machine, even that other machine having another operating system.

Then, try it:

    python3 pyempaq-example.pyz

You should see the project's reportings that we mentioned above (**note**: these lines will be surrounded by debug ones that will be hidden by default in the future):

    Hello world
    Code access ok .../pyempaq/projectname-20210722013526/orig/src/foo.py
    Media access ok
    Module requests imported .../pyempaq/projectname-20210722013526/venv/lib/python3.8/site-packages/requests/__init__.py

This shows that what you've run actually started, accessed the internal modules and other files, and imported correctly a custom-installed dependency.


## How to contribute to the project?

Please check [the how to contribute](https://github.com/facundobatista/pyempaq/blob/main/CONTRIBUTING.md) instructions.
