import json

from ..config import Config
from ..constants import CONFIG_PATH


def _add_password_to_config(password):
    with open(CONFIG_PATH, "r") as f:
        file_content = json.load(f)
        file_content["is_auto_fill_password"] = {"status": True, "value": password}

    with open(CONFIG_PATH, "w") as f:
        json.dump(file_content, f)


def _remove_password_from_config():
    with open(CONFIG_PATH, "r") as f:
        file_content = json.load(f)
        file_content["is_auto_fill_password"] = {"status": False, "value": None}

    with open(CONFIG_PATH, "w") as f:
        json.dump(file_content, f)


def set_config(config: Config):
    if config.is_auto_fill_password == "true":
        _add_password_to_config(config.password)
    elif config.is_auto_fill_password == "false":
        _remove_password_from_config()
