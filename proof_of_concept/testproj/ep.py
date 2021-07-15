import os

print("Hello world")

from src import foo  # NOQA
print("Code access ok", foo.__file__)

os.access("media/bar.bin", os.R_OK)
print("Media access ok")

import requests
print("Module requests imported", requests.__file__)
