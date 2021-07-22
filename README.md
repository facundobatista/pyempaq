# PyEmpaq

A simple but powerful Python packer to run any project with any virtualenv dependencies anywhwere.

**FIXME**: explain the idea more descriptive. Include multiplatorm capabilities (pack and run in linux and windows and between them).


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
