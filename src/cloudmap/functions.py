import os
import asyncio
import sqlite3

from ..utils import read_file, write_file
from ..constants import (
    CONFIG_PATH,
    CLOUDMAP_DB_PATH,
    STORED_PREPARED_FILE_PATHS,
)


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


async def update_cloudmap(cloudmap):
    def update():
        conn = sqlite3.connect(CLOUDMAP_DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO cloudmap VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cloudmap["channel_id"],
                cloudmap["msg_id"],
                cloudmap["file_path"],
                cloudmap["file_name"],
                cloudmap["file_size"],
                cloudmap["checksum"],
                cloudmap["time"],
            ),
        )

        conn.commit()
        conn.close()

    await asyncio.to_thread(update)


def get_cloudmap():
    channel_id = get_cloud_channel_id()

    conn = sqlite3.connect(CLOUDMAP_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM cloudmap where channel_id=?
        """,
        (channel_id,),
    )

    result = cursor.fetchall()
    conn.close()

    return [dict(i) for i in result]


def get_pushed_file_paths():
    channel_id = get_cloud_channel_id()

    conn = sqlite3.connect(CLOUDMAP_DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT file_path FROM cloudmap where channel_id=?
        """,
        (channel_id,),
    )

    result = cursor.fetchall()
    conn.close()

    return [i[0] for i in result]


def get_pushed_file_names():
    channel_id = get_cloud_channel_id()

    conn = sqlite3.connect(CLOUDMAP_DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT file_name FROM cloudmap where channel_id = ?
        """,
        (channel_id,),
    )

    result = cursor.fetchall()
    conn.close()

    return [i[0] for i in result]


def get_pushed_checksums():
    channel_id = get_cloud_channel_id()

    conn = sqlite3.connect(CLOUDMAP_DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT checksum FROM cloudmap where channel_id=?
        """,
        (channel_id,),
    )

    result = cursor.fetchall()
    conn.close()

    return [i[0] for i in result]


def clean_prepared_data():
    for path in os.listdir(STORED_PREPARED_FILE_PATHS):
        file_path = os.path.join(STORED_PREPARED_FILE_PATHS, path)
        os.remove(file_path)
