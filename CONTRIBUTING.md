# How to contribute to the project

General ideas, tips, commands.


## Setup

Create a virtualenv, activate, install requirements, check it works:

    $ python3 -m venv env
    $ source env/bin/activate
    (env) $ pip install -r requirements-dev.txt
    (env) $ python -m pyempaq --help
    usage: __main__.py [-h] source
    
    positional arguments:
      source      The source file (pyempaq.yaml) or the directory where to find it.
    
    optional arguments:
      -h, --help  show this help message and exit

## Run tests

Get into the virtualenv, and:

    (env) $ python -m pytest tests/


## About style

We do flake8 and pep257. The tests include checks for those.

We do NOT do black.
