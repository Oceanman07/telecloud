import os
import asyncio

from ..utils import read_file, write_file
from ..constants import (
    CONFIG_PATH,
    CLOUDMAP_PATH,
    STORED_PREPARED_FILE_PATHS,
)


async def update_cloudmap(cloudmap):
    await asyncio.get_running_loop().run_in_executor(
        None, write_file, CLOUDMAP_PATH, cloudmap, "w", True
    )


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


def load_cloudmap(func):
    cloudmap = None
    if os.path.exists(CLOUDMAP_PATH):
        cloudmap = read_file(CLOUDMAP_PATH, mode="r", deserialize=True)

    def load():
        nonlocal cloudmap
        if cloudmap is None:
            cloudmap = read_file(CLOUDMAP_PATH, mode="r", deserialize=True)
        return func(cloudmap)

    return load


@load_cloudmap
def get_cloudmap(cloudmap):
    return cloudmap


@load_cloudmap
def get_existed_file_names_on_cloudmap(cloudmap):
    """
    Get all the file names of pushed files for naming pulled files
    it cannot use `set` to deduplicate for smaller size
    since a single file has multiple uploads means it has changed a lot
    so when pulling we will have all the changed version of that file with file name = file_name + msg_id + time
    """
    return [os.path.basename(cloudmap[msg_id]["file_path"]) for msg_id in cloudmap]


@load_cloudmap
def get_existed_checksums(cloudmap):
    """
    Get all the checksums of pushed files for checking if a file is changed or not
    if it doesnt change then no need to push again
    a lot of files may have the same content so use `set` to deduplicate for faster checking
    """
    return set([cloudmap[msg_id]["checksum"] for msg_id in cloudmap])


@load_cloudmap
def get_existed_file_paths_on_cloudmap(cloudmap):
    # like get_existed_checksums
    return set([cloudmap[msg_id]["file_path"] for msg_id in cloudmap])


def clean_prepared_data():
    for path in os.listdir(STORED_PREPARED_FILE_PATHS):
        file_path = os.path.join(STORED_PREPARED_FILE_PATHS, path)
        os.remove(file_path)
