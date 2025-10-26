import asyncio
import sqlite3

from .config_manager.config_loader import get_cloud_channel_id
from .constants import CLOUDMAP_DB_PATH


def create_cloudmap_db():
    conn = sqlite3.connect(CLOUDMAP_DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cloudmap (
            channel_id INTERGER,
            msg_id INTERGER,
            file_path TEXT,
            file_name TEXT,
            file_size INTERGER,
            checksum TEXT,
            time TEXT
        )
        """
    )

    conn.commit()
    conn.close()


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


def delete_pushed_files():
    channel_id = get_cloud_channel_id()

    conn = sqlite3.connect(CLOUDMAP_DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM cloudmap where channel_id = ?
        """,
        (channel_id,),
    )

    conn.commit()
    conn.close()
