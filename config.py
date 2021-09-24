import json
import os
import typing as ty

with open("config.json", encoding="utf-8") as config_file:
    config: ty.Dict[str, str] = json.load(config_file)

for key, value in config.items():
    os.environ[key] = value

del config_file, config
