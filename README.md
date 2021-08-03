# PyEmpaq

A simple but powerful Python packer to run any project with any virtualenv dependencies anywhwere.

With PyEmpaq you can convert any Python project (see limitations below) in a single `.pyz` file with everything packed inside. 

That single file is everything that needs to be distributed. When the final user executes it, the original project will be expanded, its dependencies installed in a virtualenv, and then it will be executed.

Both the packaging and the execution are fully multiplatorm. This means that you can pack a project in Linux, Windows, Mac or whatever, and it will run ok in Linux, Windows, Mac or whatever.

# FIXME

Create three examples here:
- something pure terminal, very small, like a fortune cookie teller
- a game with arcade
- Encuentro with Qt

.. image:: resources/logo-256.png


### How does this work?

There are two phases: packing and execution. 

The **packing** is run by the project developer, once, before distribution. It's a simple step where the developer runs PyEmpaq indicating all needed info, and PyEmpaq will produce a single `<projectname>.pyz` file. That's all, and that only file is what is needed for distribution.

In this packing phase, PyEmpaq builds the indicated packed file, putting inside:

- the payload project, with all the indicated modules and binary files (currently *everything*, but this will be improved in the future)

- an *unpacker* script from PyEmpaq, which will be run during the execution phase

- a little more needed infrastructure details for the `.pyz` to run correctly

After packing, the developer will distribute the packed file, final users will download/receive/get it, and execute it.

To execute it, all that needs to be done is to run it using Python, which can be done from the command line (e.g. `python3 supergame.pyz`) or by doing double click from the file explorer in those systems that relate the `.pyz` extension to Python (e.g. Windows).

In this execution phase, the *unpacker* script put by PyEmpaq inside the packed file will be run, doing the following steps:

- will check if has needed setup from a previous run; if yes, it will just run the payload project with almost no extra work; otherwise...

- will create a directory in the user data dir, and expand the `.pyz` file there

- will create a virtualenv in that new directory, and install all the payload's project dependencies

- will run the payload's project inside that virtualenv

The verification that the unpacker does to see if has a reusable setup from the past is based on the `.pyz` timestamp; if it changed (a new file was distributed), a new setup will be created and used.


### Command line options

**Note**: in the future we will migrate to a more expresive `pyempaq.yaml` config for the project, which will declare this variables and others, and will not use command line arguments to specify them.

These are the current options:

- `basedir`: the root of the project's directory tree
- `entrypoint`: what to execute to start the project
- `--requirement`: (optional, can be specified multiple times) the requirements file with the project's dependencies


### The configuration file

*(We don't have one YET, currently all options are indicated through command line, but will migrate to having a config file soon.)*


### Limitations:

There are some limitations, though:

- Only Python >= 3.6 is supported

- Only Linux, Windows and Mac is supported

- Only pip-installable dependencies are supported.

- Only dependencies that are pure Python or provide wheels are supported.

If you have any ideas on how to overcome any of these limitations, let's talk!


## A simple try for the example

The project comes with a small example project. Just a couple of dir/files under `example`:

- a `src` and `media`, with stuff to be imported and accessed

- a `requirements.txt` which declares a simple dependency

- a `ep.py` file which is the project's entrypoint; all it does is to inform i started, import the internal module, access the media files, and use the declared dependency, reporting every step.

This explores most of the needs of any project. You can try this example, and will be ready to actually try any other project you want.

So, let's pack the example:

    python3 -m pyempaq example/ example/ep.py --requirement=example/requirements.txt

That command executed the PyEmpaq project specifying:

- the base directory of the project to pack (all its subtree will be packed)

- the entry point to execute the project

- one or more requirement files specifying the project's dependencies

**Note**: in the future we will migrate to a more expresive `pyempaq.yaml` config for the project, which will declare this variables and others, and will not use command line arguments to specify them.

After running that command, you will see a `projectname.pyz` file (**note**: the project's name is hardcoded so far, this will change in the future). That is the **whole project encoded in a single file**.

At this point you may move that `projectname.pyz` to another directory, or to another machine, even that other machine having another operating system.

Then, try it:

    python3 projectname.pyz

You should see the project's reportings that we mentioned above (**note**: these lines will be surrounded by debug ones that will be hidden by default in the future):

    Hello world
    Code access ok .../pyempaq/projectname-20210722013526/orig/src/foo.py
    Media access ok
    Module requests imported .../pyempaq/projectname-20210722013526/venv/lib/python3.8/site-packages/requests/__init__.py

This shows that what you've run actually started, accessed the internal modules and other files, and imported correctly a custom-installed dependency.
