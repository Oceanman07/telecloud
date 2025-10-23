import os

from ...utils import read_file, write_file
from ...constants import CONFIG_PATH


def update_config(config):
    write_file(CONFIG_PATH, config, mode="w", serialize=True)


def load_config(func):
    config = None
    if os.path.exists(CONFIG_PATH):
        config = read_file(CONFIG_PATH, mode="r", deserialize=True)

    def load():
        nonlocal config
        if config is None:
            config = read_file(CONFIG_PATH, mode="r", deserialize=True)
        return func(config)

    return load


@load_config
def get_config(config):
    return config


@load_config
def get_api_id(config):
    return config["api_id"]


@load_config
def get_api_hash(config):
    return config["api_hash"]


@load_config
def get_cloud_channel_id(config):
    return config["cloud_channel_id"]


@load_config
def get_encrypted_symmetric_key(config):
    return config["encrypted_symmetric_key"]


@load_config
def get_default_pulled_directory(config):
    return config["pulled_directory"]
